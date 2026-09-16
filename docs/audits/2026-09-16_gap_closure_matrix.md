# Gap-Closure Matrix — external review round 2

**Date:** 2026-09-16 · **Supersedes the matrix in
`2026-09-16_verification_and_corrections.md`** for the items below.

This document separates three things that were previously conflated:

| Column | Means |
|---|---|
| **Implemented** | The change exists in the tree, with the file that carries it. |
| **Isolated verification** | Checks run against a scratch database / temp store / stubbed boundary, in this tree, with the command and result. |
| **Live verification** | Checks run against the RUNNING backend (`localhost:8001`) or the operator's real store, with the command and result. |

A row may be implemented and isolated-verified while live verification is
**pending a restart** — that distinction is the point of this document.

---

## Tested revision

| Thing | Value |
|---|---|
| HEAD | `a3aa31ba4` (previous round `315d60445`, `c31316004`) |
| Working tree | HEAD + uncommitted changes; the files this round touched are listed per row below |
| Backend process | pid **11051**, started **2026-09-16T13:49:31Z**, `GET /api/health` → `git_commit a3aa31ba4` |
| Database (live) | `/Users/rushiparikh/projects/atom/backend/data/atom.db` |
| BYOK store (live) | `/Users/rushiparikh/projects/atom/backend/data/byok_keys.json` |
| Test interpreter | `backend/venv/bin/python` (3.11) for tests; the live server runs `backend/venv314` (3.14) |

### Effective configuration at verification time

Read from the live process (`GET /api/v1/admin/settings`, authenticated as an
admin user; `source` is the resolver's own provenance field):

| Setting | Value | Source |
|---|---|---|
| `ATOM_FABRICATION_BENCH` | True | default |
| `ATOM_FABRICATION_BENCH_MIN_EVENTS` / `_RATE` / `_WINDOW_HOURS` | 3 / 0.25 / 48 | default |
| `ATOM_EVIDENCE_BUDGET_CHARS` | 18000 | default |
| `ATOM_LEARNING_ROUTER` | auto | **db** (runtime-settings override) |
| `ATOM_LEARNING_ROUTER_AUTO_MIN_ROWS` / `_MIN_MODELS` / `_MIN_PER_MODEL` | 30 / 2 / 8 | default |
| `ATOM_SANDBOX_FORCE_ENFORCE` | True | default |
| `ATOM_TEMPORALITY_ENABLED` | True | default |

---

## Matrix

### 1. Credential resolution — scoped, ownership-preserving

| | |
|---|---|
| **Implemented** | `core/byok_endpoints.py` (`_entry_scope`, `_find_stored_key(tenant_id=…)`, `APIKey.tenant_id` round-trip, `is_configured` defined AS the getter), `api/byok_routes.py` (same resolver, global-only unscoped lookups, per-tenant health count), `core/llm_credential_service.py`, `core/llm/byok_handler.py` (one scoped resolution call instead of guard-then-getter) |
| **Isolated verification** | `pytest tests/test_byok_key_store_resolution.py` → **34 passed** (two-tenant collision both insertion orders, global-vs-scoped precedence, inactive keys, failed decryption, reload, and `is_configured ⇔ retrievable` per caller/scope).<br>`./venv/bin/python scripts/redteam_byok_scope_resolution.py` → **9/9 contained**, with **6 cases where the in-flight resolver returned a credential the corrected contract refuses or reassigns** (tenant `globex` received tenant `acme`'s key; an unscoped lookup was served a scoped credential).<br>`pytest tests/unit/test_byok_handler.py` → **4 failed / 193 passed = the pristine-HEAD worktree baseline exactly** (`git worktree add /tmp/atom-head c31316004`), so no regression. |
| **Live verification** | `POST /api/ai/providers/{deepseek,opencode-go,openrouter}/test` → **ok/ok/ok**; `GET /api/ai/providers/{p}` → `has_api_keys=True, has_tenant_key=True, status=active` for all three; `GET /api/ai/health` → `{total: 37, active: 3, with_keys: 3}`. |
| **Live verification — and its ceiling** | A real completion per provider (in-process, same store, one token): `deepseek` **COMPLETION OK**, `openrouter` **COMPLETION OK**, `opencode-go` **`AuthenticationError: 401 Invalid API key`**. So the credential now RESOLVES and the client is CONSTRUCTED for all three, and two of three actually serve a request — but **`opencode-go`'s stored key does not authenticate a completion**, and the `/test` endpoint reported `ok` for it because that probe only calls `models.list()`, which this gateway answers without validating the key. See "Retained limitations". |
| **Before** | Only `ollama` + `openrouter` had clients; `deepseek`/`opencode-go` resolved to `None` although both keys were in the store. |

**Precedence contract, stated once:** a caller that declares a tenant gets its
own scoped entry, else the operator's global entry, never another tenant's; a
caller that declares none gets the global entry, else a single-scope store
resolves to that one scope, and **two or more scopes refuse** (`None`, logged).
The store beats the environment variable, which is never persisted.

### 2. Implementation completion vs deployment verification

| | |
|---|---|
| **Implemented** | No new product code. Sequencing + a new harness: `backend/scripts/verify_isolated_api_boundary.py` |
| **Isolated verification** | `./venv/bin/python scripts/verify_isolated_api_boundary.py` → **14/14 checks passed** against a real isolated uvicorn instance with a scratch SQLite database: instance boots and reports the scratch store; public login works; 56 RPC actions enumerate and **no public action exposes raw app-DB SQL**; three raw-SQL probes through the RPC boundary leak nothing; the app-DB attack set is **15/15 contained against the scratch DB**; the verdict lifecycle writes 5 rows for 5 generations, annotates the judged generation exactly once, and re-reads from a fresh session as `generations=5, fabricated=2, rate=0.4`. |
| **Live verification** | Restart taken three times as edits landed (2908 → 6878 → **11051**); the last occurred after every backend edit in this round. `GET /api/health` → pid 11051, started 13:49:31Z, `git_commit a3aa31ba4`, db `data/atom.db`, byok store `data/byok_keys.json`. Settings table above read from the live process. **Ordinary feedback persistence: 1 live chat turn took `llm_routing_feedback` from 375 → 379 rows**, newest rows carrying the real 16-feature vector. |
| **Ownership** | Recorded in `AGENT_COORDINATION.md` (09:19, 09:37, 09:42 GO, 09:50 results). A concurrent session committed the item-1 work as `315d60445`; the file content matches this tree byte-for-byte (`git diff 315d60445 -- backend/core/byok_endpoints.py` is empty). |

Twenty minutes of quiescence was **not** treated as relinquishment: the shared
file was re-hashed immediately before each edit, one edit was rejected by the
tool because the file had changed underneath it, and that change was read and
reconciled rather than overwritten.

### 3. Feedback accounting at the generation level

| | |
|---|---|
| **Implemented** | New `core/llm/fabrication_accounting.py` (turn/attempt/generation/verdict identities, per-row failure isolation); `core/llm/byok_handler.py` bench now divides **fabricated generations / evaluated generations**; `core/learning_llm_router.py` verdict writes are **idempotent per generation** (same verdict → no new row; different verdict → annotate the same row); `core/llm/learning_router_registry.py` accepts `routing_result_id`; `core/llm_service.py` publishes the generation id in the result payload; `integrations/chat_orchestrator.py` passes it back from both guards. |
| **Isolated verification** | `pytest tests/test_fabrication_accounting.py tests/test_fabrication_bench.py` → **60 passed**, including: one fabrication among four evaluated generations is **1/4 not 1/5**; primary and fallback attempts stay distinct; repeated corrections collapse; JSON `null` / array / truncated JSON / garbage / scalar payloads are per-row and cannot fail the whole check open; durable DB contents and restart behaviour asserted (not call counts). |
| **Live verification** | `account_generations()` over the live 48 h window: **379 rows → 244 evaluated generations, 0 fabricated, 134 unknown, 1 duplicate row collapsed, 0 malformed** (67 rows were being mis-reported as malformed before the JSON-`null` fix). `verdict_counts = {}` — **0 of 379 live rows carry any verdict**, so the numerator is still empty. |
| **Honest statement** | The bench's denominator is now the right unit and its refusals are legible. It is **not** yet evidence that any model is honest or dishonest: absence of provenance in a history that carries no provenance at all cannot establish absence of fabrication. |

### 4–5. Reliability harness + fallback independence

| | |
|---|---|
| **Implemented** | `backend/scripts/provider_reliability_replay.py`: explicit per-probe **answer contracts** (transport success is recorded separately from contract satisfaction); **first-visible latency from actual streamed output** (first content-bearing chunk, not a post-completion stamp); per-attempt telemetry — requested vs used `(provider, model)`, retry index, structured error, token usage, cost with an explicit `cost_unknown`; retry and spend caps enforced in the loop and printed; four-state topology (`some_shared_fallbacks` / `all_shared_fallbacks` / `no_fallback` / `unknown_topology`); fixture limitations encoded as expectations (`unsupported_by_fixture` probes leave the contract pass rate); indirect-write guard. Coverage: `backend/tests/test_provider_reliability_replay.py`. |
| **Isolated verification** | `pytest tests/test_provider_reliability_replay.py`; pure parts (contracts, caps, topology classification, first-visible extraction from a synthetic chunk stream) asserted without network. |
| **Live verification (bounded, 3 calls)** | `backend/scripts/provider_reliability_live_20260916.json` (2026-09-16T13:50:52Z, mode `stream`): **contract_pass 0/2** (1 probe excluded as `unsupported_by_fixture`), transport success 1/3, zero-output 0/3, rate-limited 0/3, `non_answer_looking_replies` 2/3. Topology: **`all_shared_fallbacks`** — primary `opencode-go / gpt-5.3-codex-spark` with three fallbacks, all `opencode-go`. Per-attempt error recorded for the primary: `401 Invalid API key`. |
| **Fixture limitations, as measured** | medium fixture: 40 rows bound to `machine <i>`; **0 regex hits for `F-5216`** → an expected list price for it is not justified and is excluded from the pass rate. large fixture: row R235 does state `LIST Price=7519.0`, so that expectation **is** checked; its formula string is **not** checkable (F235/H235 are never defined). |
| **Read-only: checked, not assumed** | Row counts identical before/after across three tables (`llm_routing_feedback` 399, `rate_usage_records` 13 384, `llm_stage_router_audit` 5; **0 rows added**). The check found that the harness WOULD otherwise write learning rows — a guard over `BYOKHandler._record_outcome_feedback` suppressed **7** calls during the run. |
| **Corrected claim** | Shared OpenRouter routing is a **common gateway dependency**. A 429 observed through that gateway does not prove every downstream route was affected; the harness says exactly that instead of "the fallbacks share the failing upstream". |
| **Not claimed** | A top-level call count does not bound internal retries or spend — the caps are now explicit and reported, but the sample is **3 attempts**, which characterises the harness, not the workload. |

### 6. Router comparison labels and calculations

| | |
|---|---|
| **Implemented** | `backend/scripts/router_evidence_report.py` rewritten to run the **actual** rankers over an identical candidate set (`get_ranked_providers` vs `_rerank_with_learning`, with `same_candidate_set` asserted), descriptive statistics renamed `observed_satisfaction_ranking` / `historical_spend_ranking`, **cost per answer** with its denominator beside every figure, no totals compared across different answer counts, fabrication accounting delegated to `core.llm.fabrication_accounting`. |
| **Isolated verification** | `pytest tests/test_router_evidence_report.py` → **29 passed**. Read-only proof: full runs including the live A/B leave the frozen DB copy byte-identical (`rows=379 data_digest=a15aabdcc9c115d0 file_digest=52ef37db743e0857` before and after). |
| **Live verification** | Regenerated against `data/atom.db`: **21 of 24 request profiles produce a different order and a different top candidate** (e.g. `general`/125-candidate at MODERATE: BPC top `gpt-5.3-codex-spark`, learned promotes `deepseek/deepseek-v4-flash-0731` from rank 15 to rank 0). Cost per answer: deepseek **0.000167/48 answers**, glm **0.000356/110**, gemini **0.000579/7**, qwen **0.001165/101**; saving expressed per answer (**0.000998/answer cheaper, 85.7 %**) with both denominators stated. |
| **Removed claims** | "learned order" / "static BPC order" as names for two descriptive statistics; any savings figure computed from incomparable totals; any implication that the observational holdout establishes superiority (**INCONCLUSIVE**, by construction). |
| **Retained limitation** | The live per-model predictor path is **not** exercised: `_per_model_routers` buckets are empty in a fresh process, so the learned order in this run is the EMA term even though `.pkl` predictors exist on disk. No candidate-order log persists. |

### 7. Evidence ceiling and relevant reads

| | |
|---|---|
| **Implemented** | `integrations/chat_orchestrator.py`: `_enforce_evidence_budget` is now a **hard** bound (`len(out) <= ATOM_EVIDENCE_BUDGET_CHARS`), claiming the budget in a defined order — decisive lines (via the existing `prompt_budget.decisive_kind`), their **attribution** (`full:`/`open:` line) and following neighbour, then everything else — and **reporting what it dropped** (decisive vs other). New `_account_turn_prompt` measures the **complete prompt** (every message) against the selected model's context window minus its output reservation, logs the breakdown, and re-trims the evidence section on overflow. |
| **Isolated verification** | `pytest tests/test_verbatim_evidence_generalization.py tests/test_prompt_budget_accounting.py` → **53 passed**, including the two cases the review named: **protected rows alone exceed the budget** (40 decisive rows, 1200-char budget → output ≤ 1200 with the decisive omissions counted) and **oversized unprefixed prose** (120 lines with no `-`/`R`/`FORMULAS` prefix → trimmed, not passed through). Also: a kept decisive row keeps its `full:` path and its neighbour; a single 50 000-char line still respects the cap. |
| **Live verification** | Not separately observable end-to-end on a normal turn (the accounting logs `[prompt-budget] …` at INFO); verified by the two suites and by the isolated instance booting with the same code. |
| **Reuse, not new mechanism** | The selector reuses `core/llm/prompt_budget.py` (`decisive_kind`, `count_tokens`, `context_window_for`, `account_prompt`); mid-document retrieval reuses the existing `relevant_window` + VFS `cat` hop in `_auto_open_top_citation`. No new search mechanism was created. |

### 8. Independent corpus at the API boundary

| | |
|---|---|
| **Implemented** | `backend/tests/test_independent_corpus_api_boundary.py` — an unseen corpus driven through the real chat route (`integrations/chat_routes.py`) with the auth dependency overridden, the planner REAL, the knowledge store stubbed at the provider seam, and the model replaced by a recorder that captures the exact evidence it was asked to answer from. |
| **Isolated verification** | `pytest tests/test_independent_corpus_api_boundary.py` → **15 passed**. Scenarios: mail, workbook (row **plus its formula**, and the formula renders only for the matched row), document, explicit inventory request, conflicting provenance (both sources assembled and labelled; the answer states the conflict and does not average), missing evidence (the invented figure is caught and never reaches the user), and a changed follow-up subject (turn 2 grounded in the new source; the prompt carries no assistant echo of source A). Each asserts BOTH the selected source (the assembled evidence) and the grounded answer (the HTTP response body). |
| **Defect found and fixed** | The corpus found a real provenance defect: `_participant_mail_rows` scanned `val.split("<", 1)[0]`, which for a bare address is the whole `local@domain.tld`, so the **domain** donated "participant names". A document question containing the ordinary word "tooling" pulled an unrelated supplier's invoice (`$3,975.00`) into the evidence under the header "the messages the user is pointing at". Fixed in `integrations/chat_orchestrator.py` by stripping every @-token before scanning; both halves are pinned (the domain no longer donates a name, a real display name still matches). It was filed as a strict `xfail` first, which failed the moment the fix landed — that is the red/green evidence. |
| **Regression check** | `pytest tests/test_chat_orchestrator.py tests/test_planner_natural_routing.py tests/test_verbatim_evidence_generalization.py tests/test_independent_corpus_api_boundary.py tests/test_attachment_evidence_general.py` → **124 passed**. |
| **Kept separate** | Cache identity isolation and office-file authorization are asserted as **distinct** properties (the corpus asserts neither implies the other); unsupported legacy extraction (`.doc`/`.ppt` → `unsupported_format`) is asserted only as an accurate report, not as a capability. |

---

## Measurements with denominators (replacing "high first-attempt reliability")

The previous report's §4 said "the platform's first-attempt reliability on this
traffic is high". That is not a measurement. What the data supports:

| Measurement | Value | Denominator | Source |
|---|---|---|---|
| Routing outcomes, live table | 399 rows / 398 generations / 267 turns | — | `router_evidence_report.py`, 13:50:10Z snapshot |
| Answered vs failed generations | 266 answered / 132 failed | 398 generations | same |
| Verdict provenance | **0** rows carry `prompt_features.verdict` | 399 rows | live DB query |
| Evaluated generations for fabrication | 264 evaluated (0 fabricated), 134 unknown | 398 generations | `account_generations()` |
| Observed fallbacks in the ladder | all ranked candidates came from `openrouter` **before** item 1 | 9 candidates | prior topology run |
| Retries observed | 1 primary→fallback pair | 168 generations (previous snapshot) | prior run |
| Duplicate writes | 2 rows for 2 generations | 168 generations (previous snapshot) | prior run |
| Live turns executed for this round's verification | 4 chat turns | 4 attempts | this session |
| Model/provider diversity observed after item 1 | `deepseek-v4-pro` recorded — a model served by the `deepseek` provider client | 14 most recent rows | live DB |

**Data-quality finding (not attributable to a fix):** one turn
(`65ac1668-…`, written 13:42:04–13:42:19Z) contributed **129 rows, one per
candidate model, all `success=false`, no cost**. That is a candidate
enumeration written into the outcome table, not 129 executed generations. Any
per-model rate computed over rows right now would blame 129 models that never
ran. The router report detects this shape (`suspected_candidate_sweeps`) and
excludes it; the fabrication accounting counts each as its own generation
because nothing distinguishes them structurally. **Filed, not fixed.**

---

## Open items

### Closed by this round (removed from the open list)

| Item | Evidence |
|---|---|
| BYOK provider resolution (5c) | keys now RESOLVE and clients are constructed for all three (was one); `deepseek` + `openrouter` complete successfully; 9/9 red-team; 34 tests. `opencode-go` resolves but its completion 401s — see "Retained" |
| Corrective-signal double write (2c) | idempotent verdict annotation; 5 rows for 5 generations in the isolated instance |
| Decisive lines and unprefixed prose escaping the evidence budget (6a/7) | hard bound + both named test cases |
| Total input-token accounting and per-model output reservation (6c) | `account_prompt` wired into the turn; measured breakdown logged |
| Relevant-window auto-open instead of head/tail (6d) | `relevant_window` is the existing mechanism and is wired in `_auto_open_top_citation` |
| "Learned order"/"static BPC order" mislabelling (6) | renamed; the real rankers are compared |
| App-DB SQL boundary + verdict lifecycle at an API boundary | `verify_isolated_api_boundary.py` 14/14 |
| Generalization beyond the suites that shipped with the code | independent unseen corpus, 15 passed at the chat API boundary, spanning 7 scenarios |
| Participant lane treating a sender's DOMAIN as a participant name | found by that corpus, fixed, regression test on both halves |

### Retained, with the reason

| Item | Why it stays open |
|---|---|
| Fabrication rate for any model | **0 verdicts exist in live history.** The bench is correct and idle; it becomes evidence only after the guards stamp rows. |
| `.doc` / `.ppt` extraction | Explicitly out of scope for stabilization: reported as `unsupported_format` + `extraction_supported: False`, which is accurate. Separate capability task (LibreOffice headless; `core.workbook_runtime._find_soffice` is the existing discovery helper). |
| Office-file per-user authorization | Distinct property from cache identity isolation; single-tenancy settles ownership of the data, not which user may read it. Not migrated (paths are persisted on canvas rows; needs a backfill). |
| Cache identity isolation | Verified for the sheet probe cache; **not** the same property as office-file authorization and not evidence for it. |
| 129-row candidate sweep in `llm_routing_feedback` | Detected and excluded from the router report; the writer could not be attributed from the table alone (129 rows at one second, identical task-default features, `success=false`, no cost). |
| `POST /api/ai/providers/{p}/test` can report a **false OK** | It probes `models.list()` only. `opencode-go` answered that endpoint while a real completion returned `401 Invalid API key`. Treat the endpoint as reachability, not authentication. Filed, not fixed. |
| `opencode-go` credential does not authenticate a completion | Live-measured (`401`), distinct from "the key is configured", which is now true. The routing ladder still contains that provider's models, so it can be selected and fail — which the reliability harness now records rather than hides. |
| Live per-model predictor path | Buckets are empty in a fresh process; the served learned order in this run is the EMA term. |
| Provider-model identity in production lookups | The harness preserves `(provider, model)`; any production lookup keyed on model **name** alone would lose provider identity when the same model is served through several gateways — reported, not fixed. |

### Claims deliberately NOT made

- No superiority claim for any ranker: the holdout is observational, and an
  unexecuted alternative has no outcome.
- No "the platform is reliable" claim: the numbers in the table above are the
  claim, with their denominators.
- No "the fallbacks share the failing upstream" claim. The measured topology is
  `all_shared_fallbacks` (primary `opencode-go / gpt-5.3-codex-spark`, three
  fallbacks, all `opencode-go`): that is a **common gateway dependency**. A
  failure observed through one gateway does not prove every downstream route
  behind it was affected, and the harness says so rather than asserting it.
- No claim that the fabrication bench has measured anything yet.
