# README feature-readiness — corrected coverage report

**Date:** 2026-10-31 (verifier correction)
**Branch:** `codex/readme-feature-readiness`
**Base checkpoint:** tag `local-core-2026-10-30-final` (`da9cc8b12de3639f59cc5b8ea84338c5f507dc6d`)
**README:** `README.md` sha256 `392b3ca2fe88cb94c326f02318bc46273da972736b807f793c3ae8246b2bcce0`

> **Status: not accepted.** This replaces the earlier 100/123 self-assessment
> after the verifier's four findings. The denominator is unchanged. The
> corrected score is lower because source-inspection, unconditional and
> status-only assertions no longer count. Independent verifier review is still
> required; this is not a release declaration and no deployment was performed.

---

## 1. Corrected result

| Measure | Value |
|---|---|
| Eligible functional claims (unchanged denominator) | **123** |
| Verified functional claims | **83** |
| Coverage | **67.5%** |
| Not verified (partial / unverified / blocked / env-limited / inaccurate) | 40 |
| Security claims (tracked separately) | 8 / 8 verified |
| Performance claims (tracked separately) | 1 / 3 verified |
| Compatibility claims (tracked separately) | 0 / 4 verified |
| Comparative marketing claims (tracked separately) | 0 / 5 verified |

The denominator was frozen before scoring by splitting the README's 17
capability categories into testable operations. The inventory still refuses to
build if the README hash or pinned commit moves
(`scripts/acceptance/readme_claim_inventory.py`). **This correction did not
change claim granularity or remove failed claims.**

### Category breakdown

| Category | Total | Verified | Not verified |
|---|---:|---:|---:|
| agent-radio | 4 | 4 | 0 |
| agent-teams | 6 | 3 | 3 |
| ask | 5 | 2 | 3 |
| core-workspace | 7 | 5 | 2 |
| gateway | 6 | 6 | 0 |
| goals | 5 | 2 | 3 |
| governance | 8 | 4 | 4 |
| graphrag | 5 | 4 | 1 |
| hybrid-search | 5 | 5 | 0 |
| installation | 5 | 4 | 1 |
| integrations | 9 | 5 | 4 |
| interoperability | 6 | 5 | 1 |
| memory | 7 | 4 | 3 |
| mini-apps | 5 | 2 | 3 |
| office | 8 | 7 | 1 |
| oracle | 6 | 5 | 1 |
| orchestration | 8 | 4 | 4 |
| routing | 7 | 3 | 4 |
| vfs | 4 | 4 | 0 |
| workflows | 7 | 5 | 2 |

Office, gateway, hybrid search, VFS, radio and interoperability are the
strongest areas. Governance, agent teams, ask/trust, memory, orchestration and
routing are materially thinner than the first report claimed.

---

## 2. What changed after the verifier review

### 2.1 Unsafe acceptance-world deletion — fixed

`common.py` previously called `shutil.rmtree()` on an environment-supplied
directory. It now:

- requires the world to be a strict child of an allowed root;
- refuses symlinked worlds and symlinked path components;
- refuses protected paths (`/`, `/Users`, home, repo, backend, temp/root);
- refuses an existing directory without the ownership marker
  `.atom-readme-acceptance-world`;
- runs the existing launcher storage guard only when the deployment's guard
  config actually governs that root;
- gives the install harness the same `reset_world()` path.

Tests: `backend/tests/test_readme_harness_world_guard.py` (10 cases:
marked-world replacement, unmarked refusal, symlink refusal, parent-symlink
refusal, outside-root refusal, root-itself refusal, protected paths, broad
root). The verifier's deletion request was safe and nothing was deleted; the
new tests cover the same boundary.

### 2.2 ORACLE-06 — replaced with executable re-delegation

The old check searched `review.py` for "re-delegation". It now runs the
conductor's PARALLEL_CONSENSUS path with a deterministic step executor and a
fake REVIEW verifier that rejects once and accepts once. Evidence:
- reviewer consulted **twice**;
- three branches executed on the first attempt and three on the second;
- the second attempt carried the feedback `"add the missing evidence"` on the
  **same step id**;
- the step completed with the revised output.

Test: `backend/tests/test_reviewer_redelegation_execution.py`.

### 2.3 GOAL-01 — replaced with a running-loop test

The old check evaluated a predicate directly and searched source text. It now
runs `GenericAgent.execute()` with a scripted `_react_step`:

- satisfying predicate at step 2 → **2 calls out of max_steps=5**;
- impossible predicate with max_steps=3 → **3 calls** (negative control).

Test: `backend/tests/test_objective_loop_termination.py`. The loop exits early,
but the returned `status` field still says `max_steps_exceeded` after the
predicate break; that is a separate shared-loop reporting defect handed to
Agent 1, not counted as a pass for a different claim.

### 2.4 SEC-06 — egress policy and negative controls

Registering a local MCP server is not proof that unauthorized destinations are
refused. `core/mcp_client.py` now validates transport/scheme/host before any
socket or process:
- only `http`/`https`/`sse` (plus command-bearing `stdio`);
- no URL credentials;
- `ATOM_MCP_ALLOWED_HOSTS` allowlist when set;
- default-deny loopback/private/link-local/reserved/multicast after DNS
  resolution.

The acceptance harness registers a permitted local server, then attempts
metadata (`169.254.169.254`), `file://`, an outside-allowlist host, and an
unknown transport through the real registration route. All return 502, no
network client is constructed (`httpx.AsyncClient` is replaced by a sentinel),
and no failed registration leaks into the server/client registries.

Tests: `backend/tests/test_mcp_client_egress.py`.

### 2.5 Search claims strengthened

- **SEARCH-02** now uses a query with **zero lexical hits** and a vector hit:
  `"parrot spotted at the rainforest treetop path"` retrieves the scarlet-macaw
  document (`lexical_hits=0`, `vector_hits=1`). Stopwords are removed from
  mixed lexical queries and the vector relevance floor is 0.25.
- **SEARCH-04** now requires a usable `citation_path`
  (`knowledge/documents/<id>/content.lines`) and resolves it through
  `documents.cat`, asserting `L1:` line numbering and the source token. An ID
  alone no longer passes.

### 2.6 Evidence integrity repaired

The prior `evidence/frontend-results.json` hash mismatch was caused by renaming
the dev-server log from `.log` (gitignored) to `.txt` after the report hash was
written. The pre-rename artifact is preserved as
`evidence/frontend-results.pre-rename.json`; its sha256 is the prior
`4b56ba3c…` value. `evidence/MANIFEST.json` and `evidence/MANIFEST.md` are
regenerated from the final evidence set and record the hash history and
superseded artifacts.

---

## 3. What the corrected verified set means

83 functional claims were executed at a user/API/service boundary with an
assertion matching the claim. Representative strong areas:

- **Office:** DOCX append with heading/table/font preserved; XLSX leading zeros
  and cross-sheet formulas with the computed value asserted; formula result +
  recalc; PPTX slide edit; present/download; paragraph-in-place sync; presented
  canvas and download survive a real backend restart.
- **Gateway:** OpenAI `/v1/chat/completions`, Anthropic `/v1/messages`,
  `/v1/models`, `atom_sk_*` create/revoke/invalid rejection, model header
  override, and a stopped upstream mapped to 502 `all_providers_failed`.
- **Hybrid search:** BM25 rare token; zero-lexical semantic retrieval; RRF
  k=60 score; citeable VFS path resolved to line-numbered content; explicit
  empty result for an absent token.
- **VFS:** ls/tree, line-numbered cat, grep, and the disabled-flag legacy
  fallback.
- **Radio:** thread create, mention-first delivery, budget refusal, timeout and
  mention wake-up.
- **Interoperability:** external MCP register/list/execute; A2A card +
  `message/send` + JSON-RPC errors; ACP initialize → session/new →
  session/prompt → agent chunk → `end_turn`; local span recording.
- **Workflows:** create/re-read; execute to completed with per-step results;
  schedule/list/remove; version + rollback recorded and re-read; completed
  execution re-read after a real process restart; starter import.
- **Orchestration:** all five conductor strategies executed through a
  deterministic executor; legal/illegal state transitions; version rollback;
  ranked specialist matching.
- **Oracle:** read-back of a real `tasks.create`; refuted self-report; enforce
  stamp and `ATOM_ORACLE_ENFORCE` pass-through; two-tier self-report vs
  external verification; executable reviewer re-delegation.
- **Core workspace:** chat turn at the served boundary; seven upload formats;
  canvas edit; goal/activity; full-vs-core product profile; chat and episode
  persistence in the core-profile world.
- **Installation:** documented backend process, 0600 bootstrap password,
  frontend dev server `/login`, task/workflow/canvas persistence across a real
  process restart.

---

## 4. Not verified (40 functional claims)

| Claim | What is missing | Status |
|---|---|---|
| ORCH-01 Queen workflow blueprint | needs a model-backed intent→blueprint turn | unverified |
| ORCH-02 Fleet open-ended task | needs a model-backed TASK turn and recruitment | unverified |
| ORCH-07 fleet routing audit row | same model-backed TASK turn | unverified |
| ORCH-08 delegation depth | `max_depth` is stored but `AgentFleetService.recruit_member` does not enforce it | **inaccurate** |
| GOV-02 execute-after-approval | queue/approve observed; no approved mutation/side effect re-read | partial |
| GOV-03 comprehensive audit trail | one HITL row inspected; no cross-action audit exercise | partial |
| GOV-04 training session | queue/proposals/complete served; session creation needs a blocked model-backed run | partial |
| GOV-05 OIDC SSO | config round-trip only; login returned 503; no IdP callback/session | partial |
| ORACLE-01 every mutating action | registry covers only `trigger_workflow` and `tasks.create` | partial |
| ASK-01 verified track record | autonomy learned from synthetic observations | partial |
| ASK-03 auto-revoke on regression | consent-gated automation needs certified production observations | partial |
| ASK-05 gated relaxation | synthetic history; admin/stats surface did not drive a real relaxation | partial |
| TEAM-01 single accountable agent | contract field constructed; no exactly-one enforcement | partial |
| TEAM-05 nightly alignment sweep | manual sweep with fake chat function; no nightly automation | partial |
| TEAM-06 incumbency baselines | one event persisted; report baselines not generated | partial |
| MEM-01 per-turn extraction | direct extractor with controlled model; `sync_turn` hook not exercised | partial |
| MEM-04 graduation | episode create/read; no graduation | partial |
| MEM-07 evolution candidate | evolution harness disabled | unverified |
| OFF-07 live broadcast | snapshot computed/persisted; no subscribed WS client | partial |
| MINI-03 dev-run | Firecracker/KVM unavailable; fails closed | environment_limited |
| MINI-04 install/state | requires Firecracker runtime | environment_limited |
| MINI-05 microVM isolation | architecture assertion; no KVM | architecture_only |
| GRAPH-05 D3 explorer | API query works; browser explorer not run | partial |
| INT-04 connected data read | live connected provider not exercised | partial |
| INT-05 outbound action | controlled send/create + HITL not exercised | partial |
| INT-07 signed webhook acceptance | forged webhook rejected; correctly signed accepted-once not exercised | partial |
| INT-09 live 46+ qualification | needs real accounts/permissions | blocked_external |
| ROUTE-03 fallback | one bounded upstream; two-provider fallback not run | partial |
| ROUTE-04 learning re-rank | status surface only; no accumulated feedback re-rank | partial |
| ROUTE-06 local provider selection | local upstream is the harness; user-selected local chat not served | partial |
| ROUTE-07 opencode-go | needs a real subscription key | unverified |
| IO-06 request tracing/export | span written directly; request-level trace + Langfuse export not run | partial |
| GOAL-02 utility target | inside the model-backed ReAct loop | unverified |
| GOAL-04 stuck detection | inside the model-backed ReAct loop | unverified |
| GOAL-05 resume/restart | create/read/cancel only; resume/restart not run | partial |
| WF-05 workflow pause/resume | needs a model-backed low-maturity agent run | partial |
| WF-07 template execution | import only; imported template not executed | partial |
| CORE-04 lesson application | lesson stored/listed; later task application not exercised | partial |
| CORE-06 Settings-to-route | provider configured/masked; no route from that Settings surface | partial |
| INST-01 full `make setup` | pristine-clone dependency bootstrap not run | unverified |

---

## 5. Defects fixed in this correction

1. **Harness world deletion boundary** — protected/symlink/unmarked-world
   refusal; ownership marker; shared install reset. Tests as above.
2. **ORACLE-06** — source-string pass replaced with a real conductor
   re-delegation test (same step, feedback, six branch executions).
3. **GOAL-01** — predicate/source check replaced with a real ReAct loop:
   2 calls with a satisfying predicate vs 3 with an impossible one.
4. **SEC-06** — MCP transport/scheme/host policy before any socket/process;
   permitted local server plus metadata/file/allowlist/transport refusals;
   no network client constructed; no leaked registration.
5. **Search** — mixed-query stopword filtering; 0.25 vector relevance floor;
   SEARCH-02 zero-lexical semantic retrieval; SEARCH-04 citeable path resolved
   through `documents.cat`.
6. **Evidence manifest** — pre-rename artifact preserved; hashes regenerated;
   hash history and superseded artifacts recorded.

Previously fixed and retained: node-based workflow versioning/rollback,
conductor context object, GraphRAG query/neighbor argument order, deterministic
GraphRAG extraction fallback, external MCP tool dispatch, vector score/floor,
truthful 67-provider catalog, episode metadata/tenant robustness.

---

## 6. Shared defects handed to Agent 1

1. **Cached BYOK key refresh.** A key stored after `LLMService` construction is
   not seen by the cached chat service; gateway works, chat says no provider
   until restart.
2. **Objective-loop status reporting.** The loop stops early at the satisfying
   predicate (call-count evidence), but the returned status remains
   `max_steps_exceeded` because the inner `run_loop` assignment does not reach
   the outer result. `GOAL-01` is counted for termination only; this bug is
   not fixed in shared agent files here.

---

## 7. Security, performance, compatibility, marketing

**Security — 8/8 verified** with the corrected SEC-06 boundary. Sandbox tier
whitelist, token ciphertext/decrypt, capability bindings, gatekeeper HITL +
masking, data-taint block, external MCP egress policy, unauthenticated API
rejection, production fail-closed without key.

**Performance — 1/3.** The test-function count is 93,825 `def test_` functions
across 3,749 files (above the 85k+ claim). The advertised `0.027 ms P99` and
`616k ops/s` figures remain unmeasured; no reproducible benchmark script was
found.

**Compatibility — 0/4 fully verified.** Python 3.11 + pinned backend stack
booted and served. The 3.12/3.13/3.14 guard matrix, PostgreSQL dialect path,
mobile build and menubar build were not executed. The README badge says
"Python 3.11+" while quickstart rejects 3.14; that wording is broader than the
tested range.

**Comparative/marketing — 0/5.** Excluded from the score. The "46+" count is a
registered 67-provider catalog with evidence, not live qualification; INT-09
remains `blocked_external`.

---

## 8. Evidence manifest

Authoritative result: `evidence/corrected-results.json`
Audit: `evidence/CLAIM_AUDIT_2026-10-31.json`
Manifest: `evidence/MANIFEST.json` / `evidence/MANIFEST.md`

The manifest contains the final sha256 for every artifact, the
`frontend-results.json` hash history (prior `4b56ba3c…` preserved as
`frontend-results.pre-rename.json`), and the superseded pre-correction
artifacts (`merged-results.json`, `all-groups.json`, `all-groups-baseline.json`).
No hash is quoted from memory.

---

## 9. Reproduction

```bash
# affected boundaries only (the verifier asked not to rerun every campaign)
python -m scripts.readme_acceptance.run \
  --groups oracle,governance,workflows,office,integrations,data,security,interop,goals
python -m scripts.readme_acceptance.run --groups gateway
# core profile + chat:
ATOM_README_PRODUCT_PROFILE=core python -m scripts.readme_acceptance.run --groups core
# install/restart/canvas:
python scripts/acceptance/readme_local_install.py

# merge + explicit audit downgrades
python scripts/acceptance/merge_readme_results.py ... --out merged.json
python scripts/acceptance/apply_readme_audit.py \
  --results merged.json --audit .../CLAIM_AUDIT_2026-10-31.json \
  --out .../corrected-results.json
python scripts/acceptance/readme_claim_inventory.py --merge .../corrected-results.json
```

Worlds are isolated, marked, and remote-effect free. The local stub is
`backend/scripts/readme_acceptance/mock_llm_server.py`; no real credentials,
sends, deployments or connected-system writes were used.
