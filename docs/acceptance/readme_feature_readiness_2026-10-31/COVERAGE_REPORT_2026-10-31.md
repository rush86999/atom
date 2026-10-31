# README feature-readiness — coverage report

**Date:** 2026-10-31
**Branch:** `codex/readme-feature-readiness`
**Base checkpoint:** tag `local-core-2026-10-30-final` (`da9cc8b12de3639f59cc5b8ea84338c5f507dc6d`)
**README:** `README.md` sha256 `392b3ca2fe88cb94c326f02318bc46273da972736b807f793c3ae8246b2bcce0`

> **Independent verifier review is required before this number is treated as
> accepted.** This report records what was actually executed in isolated worlds.
> It does not deploy, cut over, contact connected systems, or declare a release.

---

## 1. Result

| Measure | Value |
|---|---|
| Eligible functional claims (agreed denominator) | **123** |
| Verified functional claims | **99** |
| Coverage | **80.5%** |
| Not verified (partial / unverified / blocked / env-limited / inaccurate) | 24 |
| Security claims (tracked separately) | 8 / 8 verified |
| Performance claims (tracked separately) | 1 / 3 verified |
| Compatibility claims (tracked separately) | 0 / 4 verified |
| Comparative marketing claims (tracked separately) | 0 / 5 verified |

The denominator was frozen before scoring by splitting the README's 17
capability categories into testable operations. Category count alone is never
used as a score. The inventory refuses to build if the README hash or pinned
commit moves (`scripts/acceptance/readme_claim_inventory.py`).

**Partial, failed, blocked, environment-limited and architecture-only claims
are not counted as passing.**

### Category breakdown

| Category | Total | Verified | Not verified |
|---|---:|---:|---:|
| agent-radio | 4 | 4 | 0 |
| agent-teams | 6 | 6 | 0 |
| ask | 5 | 4 | 1 |
| core-workspace | 7 | 7 | 0 |
| gateway | 6 | 6 | 0 |
| goals | 5 | 3 | 2 |
| governance | 8 | 7 | 1 |
| graphrag | 5 | 4 | 1 |
| hybrid-search | 5 | 5 | 0 |
| installation | 5 | 3 | 2 |
| integrations | 9 | 6 | 3 |
| interoperability | 6 | 6 | 0 |
| memory | 7 | 6 | 1 |
| mini-apps | 5 | 2 | 3 |
| office | 8 | 7 | 1 |
| oracle | 6 | 6 | 0 |
| orchestration | 8 | 4 | 4 |
| routing | 7 | 3 | 4 |
| vfs | 4 | 4 | 0 |
| workflows | 7 | 6 | 1 |

No eligible category is entirely untested. Breadth is uneven: Office,
governance, oracle, radio, hybrid search, VFS, gateway and interoperability are
strong; orchestration, routing, mini-apps and integrations remain the thin
areas.

---

## 2. How claims were exercised

Worlds were fully isolated: throwaway SQLite database, throwaway data root,
schedulers/pollers disabled, no connected credentials, no real sends. A
bounded local server stood in for:

- OpenAI-compatible `/v1/chat/completions` and `/v1/models`
- Anthropic-compatible `/v1/messages`
- an OAuth provider consent/token exchange
- an MCP JSON-RPC server (`initialize` / `tools/list` / `tools/call`)

The harness talks through the same HTTP/WebSocket boundaries a browser or API
client uses (`backend/scripts/readme_acceptance/`). Direct service calls are
used only where the product exposes no HTTP route, and the claim evidence says
so. Installation/restart claims were exercised with the **real backend
process** (`uvicorn main_api_app:app`), not in-process.

Worlds:

| World | Groups | Purpose |
|---|---|---|
| `readme-feature-world` | all groups | breadth run |
| `readme-data-world` | graphrag, data, memory | extraction/search/VFS vector fixes |
| `readme-core-world` | core | chat with a provider present at process start |
| `readme-radio-world` | radio | lateral messaging |
| `readme-install-world` | install + restart | documented backend command, 0600 admin password, durable task + workflow execution |

---

## 3. What was verified (representative)

- **Orchestration:** conductor accepts all five strategies and rejects an
  invalid one; state machine allows legal transitions and rejects an illegal
  one; workflow version create/compare/rollback works on node-based
  definitions; ranked specialist matching selects the capability+tier+verified
  leader.
- **Governance:** STUDENT blocked / INTERN blocked / SUPERVISED pending /
  AUTONOMOUS approved on a complexity-3 action; approval executes once,
  rejection has no effect; 8-role RBAC denies a member and allows the operator;
  SCIM create/list/deactivate and unauthenticated rejection; OIDC config
  round-trip with the secret hidden.
- **Oracle:** default-on verifier registry; real `tasks.create` row read-back
  verified present, then refuted after deletion; kill switch disables checks;
  reviewer re-delegation.
- **Ask/trust:** cold start asks; synthetic verified history relaxes one action
  to allow while a destructive action stays blocked; the certification gate
  fails a weak set and passes a separable set (Brier ≤ 0.25, denial coverage
  ≥ 0.7).
- **Agent teams:** contract render with one accountable agent; default-deny
  expiring privilege lease; self-recruitment/rotation conflict checks;
  contribution credit sums to the realized outcome and dampens a late failure;
  alignment sweep runs; telemetry event persists.
- **Memory:** controlled-model per-turn extraction persisted a categorized
  fact; SQL prompt-tier and public memory search; LanceDB semantic recall of a
  paraphrase; memory_remember/forget; episode created from a real execution and
  read back.
- **Hybrid search:** BM25 rare token; semantic paraphrase; RRF (k=60) score
  formula; source/citation fields; a truly absent token returns an explicit
  empty result (after the vector relevance floor fix).
- **VFS:** ls/tree; line-numbered `cat`; `grep`; legacy fallback with the flag
  disabled.
- **Agent Radio:** thread create; mention-first delivery; budget refusal;
  empty wait timeout and mention wake-up.
- **Office:** DOCX append preserving heading/table/font; XLSX leading zeros +
  cross-sheet formulas; formula-result + recalculate; PPTX slide update;
  present/download; paragraph-in-place sync preserving table; canvas row bound
  and reloadable.
- **Mini-apps:** agent scaffold; syntax-gated logic write; runtime fails closed
  without Firecracker (not counted as a pass).
- **GraphRAG:** deterministic extraction fallback; two-hop neighborhood;
  community build; JIT citation verification against a real local file; local
  query.
- **Workflows:** create/read; execute to completed with per-step results;
  schedule/list/remove; version + rollback; starter template import; a
  completed execution re-read after a real process restart.
- **Gateway:** OpenAI `/v1/chat/completions`, Anthropic `/v1/messages`,
  `/v1/models`; `atom_sk_*` create/invalid/revoke; header model override
  reaches the upstream; a stopped upstream maps to 502 `all_providers_failed`.
- **Interoperability:** external MCP register + tools + echo execution; A2A
  card + `message/send` + JSON-RPC errors + unauthenticated rejection; ACP
  initialize/session-new; span recording with optional Langfuse export off.
- **Integrations:** truthful 67-provider business catalog with per-provider
  evidence; connected state false→true→false; controlled OAuth
  initiate→callback→token→disconnect; unsigned Shopify webhook rejected 401.
- **Core workspace:** chat turn + history; CSV/XLSX/PDF/DOCX/PPTX/EML upload
  and content retrieval; canvas edit; teaching; activity/goal runs; provider
  settings masked; full product profile.
- **Installation:** documented `uvicorn main_api_app:app` process on a fresh
  root; 0600 bootstrap password file; login; task and workflow execution
  survive a real process restart.

---

## 4. Not verified (24 functional claims)

| Claim | What is missing | Status |
|---|---|---|
| ORCH-01 Queen workflow blueprint | needs a model-backed intent→blueprint turn; no cloud key used | unverified |
| ORCH-02 Fleet open-ended task | needs a model-backed TASK turn and recruitment | unverified |
| ORCH-07 fleet routing audit row | same model-backed TASK turn | unverified |
| ORCH-08 delegation depth | `DelegationChain.max_depth` is stored but `AgentFleetService.recruit_member` does not reject a deeper link; README/CLAUDE claim is overstated | **inaccurate** |
| GOV-04 AI training session | queue/proposals/complete are served; session creation is triggered by a blocked agent run that needs a model | partial |
| ASK-03 auto-revoke on regression | consent-gated automation needs certified production observations | partial |
| MEM-07 evolution candidate | `ATOM_AGENT_EVOLUTION_ENABLED=false` in this world; separate controlled world not run | unverified |
| OFF-07 live broadcast | snapshot is computed/persisted; no subscribed browser WS client captured the frame | partial |
| MINI-03 dev-run | Firecracker is the only runtime; macOS host has no KVM (fails closed) | environment_limited |
| MINI-04 install/state | requires the Firecracker runtime | environment_limited |
| MINI-05 microVM isolation | architecture assertion; cannot be exercised without KVM | architecture_only |
| GRAPH-05 D3 explorer | API query works; browser rendering of the explorer not run | partial |
| INT-04 connected data read | controlled provider journey exists; live data qualification not run | partial |
| INT-05 outbound action | controlled provider send/create + HITL not run | partial |
| INT-09 live 46+ qualification | needs real accounts/permissions; not requested | blocked_external |
| ROUTE-03 fallback | needs two configured providers; world has one bounded upstream | partial |
| ROUTE-04 learning re-rank | status surface served; needs accumulated feedback rows | partial |
| ROUTE-06 local model route | bounded local upstream is the harness; a user-selected local-provider chat was not served | partial |
| ROUTE-07 opencode-go | needs a real subscription key; no live spend | unverified |
| GOAL-02 utility target | executes inside the model-backed ReAct loop | unverified |
| GOAL-04 stuck detection | executes inside the model-backed ReAct loop | unverified |
| WF-05 workflow pause/resume | needs a model-backed low-maturity agent run; generic HITL is verified separately | partial |
| INST-01 `make setup` | did not run the full dependency bootstrap from a pristine clone; used the pinned Python 3.11 environment | unverified |
| INST-03 frontend | frontend was not started; backend/login/API boundary verified | unverified |

**Known inaccurate/overstated marketing:** ORCH-08 (delegation depth
enforcement). The claim should be implemented or reworded.

---

## 5. Defects found and fixed

Each fix has an acceptance observation and targeted tests.

1. **Workflow versioning crashed on the second version of every node-based
   workflow** (`steps: null` iteration) → rollback returned 500.
   `core/workflow_versioning_system.py`; test in
   `tests/test_covpush_wfengine.py::test_node_based_workflow_with_null_steps`.
2. **Conductor 500 whenever `context` was supplied** — the route passed a raw
   dict where `WorkflowExecutionContext` was required. `core/workflow_endpoints.py`.
3. **GraphRAG neighbors and `/query` passed arguments positionally into
   `tenant_id`**, so entity name/mode were never used as the query.
   `api/graphrag_routes.py`; tests updated in
   `tests/test_covpush_w32_learning_graphrag_routes.py`.
4. **GraphRAG did not fall back to deterministic extraction** when the LLM
   extractor was available but returned nothing, leaving a no-key install with
   an empty graph. `core/graphrag_engine.py`; test
   `tests/test_graphrag_pattern_fallback.py`.
5. **External MCP tools were discoverable but not executable** — the legacy
   dispatcher returned `not_implemented` for servers registered through the
   real P6 client. `core/mcp_service.py` + `integrations/mcp_service.py`; the
   acceptance harness runs register → tools → `echo` end-to-end.
6. **Hybrid search treated every nearest neighbour as a result** and read
   `_distance` (defaulting to 1.0) instead of the handler's similarity
   `score`. A nonsense query returned unrelated documents. Added a 0.3
   similarity floor and score normalization.
   `core/hybrid_search/documents_hybrid.py`; tests in
   `tests/core/test_documents_hybrid.py`.
7. **The public integration catalog counted internal router modules** (97) and
   the connection-status catalog exposed 41 provider cards. Added a truthful
   67-provider business catalog with per-provider evidence (OAuth config,
   adapter, route, env key or connection source), exposed at
   `/api/integrations/business-catalog` and in `/api/integrations`.
   `core/integration_business_catalog.py`, `main_api_app.py`; tests in
   `tests/test_integration_business_catalog.py`.
8. **Episode creation failed when execution metadata was a list or tenant_id
   was NULL.** `core/episode_service.py`; the acceptance harness creates and
   reads an episode from a real chat execution.

---

## 6. Shared-execution defect to hand to Agent 1

**A BYOK key stored after `LLMService` has been constructed is not picked up by
the cached chat service.** The gateway path builds a fresh handler per request
and works; the chat path uses a thread-local `ServiceFactory.get_llm_service`
instance created earlier, so Settings → AI appears saved while chat still says
"No eligible LLM providers" until a restart. CORE-01 is verified in a world
where the provider exists at process start, not through a live Settings edit.
This is a shared Chat/LLM-lifecycle defect; it has not been patched here.

Reproduction: start a world with no provider, complete any LLM-using group,
store an `openai` key from Settings, then send `/api/chat/message`; the gateway
`/v1/chat/completions` with an `atom_sk_*` key succeeds while chat returns
`no_llm_provider`.

---

## 7. Security, performance, compatibility, marketing

**Security — 8/8 verified.** Sandbox tier whitelist; token ciphertext at rest
with decrypt round-trip and OAuth-callback wiring; capability bindings;
outbound gatekeeper HITL + masking; data-taint block; external MCP connect;
unauthenticated API rejection; production fail-closed without an encryption
key.

**Performance — 1/3 verified.** The advertised `85k+ test functions` is
supported: the tree contains **93,825** `def test_` functions across 3,749 test
files (grep count; the README's 84,737/2,759 figure is conservative). No
reproducible governance benchmark script was found for the advertised
`0.027 ms P99` / `616k ops/s` figures; those two were not measured and are not
claimed.

**Compatibility — 0/4 fully verified.** Python 3.11 + the pinned backend stack
booted and served. The 3.12/3.13/3.14 guard matrix, PostgreSQL dialect path,
mobile build and menubar build were not executed. The README's "Python 3.11+"
badge is broader than the tested range.

**Comparative/marketing — 0/5 verified.** These are comparative claims, not
functional operations, and are excluded from the score. The "46+" count is
supported only as a **registered** catalog (67 providers with evidence); live
qualification of all providers remains `blocked_external`.

---

## 8. Evidence manifest

All artifacts are under
`docs/acceptance/readme_feature_readiness_2026-10-31/`.

| Artifact | sha256 |
|---|---|
| `CLAIM_INVENTORY.json` | `3c30ba28d285d3bd64733696e0008dbb0ba428a7d9e670a8bbeac63fd2b6fe08` |
| `evidence/merged-results.json` | `40950d0beb82c19b8a93af54eac1e77486462335183c5f01b7f43c06eb6339be` |
| `evidence/all-groups.json` | `e18b410fc8db7dfa1bd2a027b676b9cc28c96467ddc740d0ce9c7146dd7e374e` |
| `evidence/data-graph-memory.json` | `a2c4bf35b224290297a7271df5e66074c738217b011d23fe22f6d2b1afa3cd84` |
| `evidence/core-chat-episode.json` | `51d0c6dcccca9100eda90d3062abcdb91f61cb9f34221d1e0201c620b3ace154` |
| `evidence/agent-radio.json` | `9c87b6211f91e1bec6b40e77618de97d538894d08bf29f2f6cc0430ea3aa9799` |
| `evidence/install-restart.json` | `901bc52a8f7ad98f32c9bfef1e9e53d981b73d8561321c3204953ad06ae7e292` |
| `evidence/test-count.txt` | `c6e0a1ed201e9b112974a8813d2281dc2aa2447ad3e90cdfa1e60a1b73c4e451` |

The merged result records every source world per claim. The inventory's
per-claim evidence paths point at the throwaway worlds; the durable copies above
are the reviewed artifacts.

---

## 9. Reproduction

```bash
# from the worktree, backend cwd
export PYTHONPATH="$OVERLAY:$REPO:$REPO/backend"

# all functional groups in one isolated world
python -m scripts.readme_acceptance.run --groups all

# focused worlds used for the merged result
python -m scripts.readme_acceptance.run --groups gateway,core \
  --out .../core-chat.json
python -m scripts.readme_acceptance.run --groups graphrag,data,memory \
  --out .../data.json
python -m scripts.readme_acceptance.run --groups radio --out .../radio.json

# documented install + real process restart (task + workflow)
python scripts/acceptance/readme_local_install.py --out .../install.json

# rebuild the frozen inventory + merge
python scripts/acceptance/merge_readme_results.py \
  --results .../all-groups.json --results .../data.json \
  --results .../core-chat.json --results .../radio.json \
  --install .../install.json --out .../merged.json
python scripts/acceptance/readme_claim_inventory.py --merge .../merged.json
```

The local upstream is `backend/scripts/readme_acceptance/mock_llm_server.py`
(OpenAI/Anthropic/OAuth/MCP). It never contacts a cloud provider and stores no
real credentials.
