# Verification & Corrections — audit follow-up (items 1–8)

**Date:** 2026-09-16 · **Basis:** independent reproduction, not code reading.
Every claim below is backed by a command in this repo or a live-DB query; the
rows marked *verified* were reproduced by a second session that did not write
the implementation under test.

**Scope split (concurrent sessions on one working tree):** items 1, 2, 4 and
part of 6 were implemented by a concurrent session; this session independently
reproduced/red-teamed those, and implemented items 3, 5, 7 and the corpus of
new boundary tests. Shared-file edits were made only after the file had been
quiescent for >20 minutes.

---

## Matrix

| # | Issue | Reproduction | Correction | Regression coverage | Boundary verification | Remaining limitation |
|---|---|---|---|---|---|---|
| **1a** | Table allowlist bypass via quoted identifiers | `scripts/redteam_app_db_boundary.py` — 4/15 attacks passed parse-time validation | sqlparse token-walk `_referenced_tables` (concurrent session) | `tests/test_app_db_query.py`, `tests/test_app_db_execution_boundary.py` | 15/15 attacks contained | — |
| **1b** | Predicate-only read of a non-allowlisted table (blind oracle) | `SELECT id FROM canvases WHERE (SELECT count(*) FROM 'users') > 0` **returned rows** | **SQLite authorizer `_db_authorizer`** — denies non-allowlisted table reads, withheld columns, ATTACH/PRAGMA and every write action | `TestInferenceChannelClosed` (3 tests) | 5/5 inference attacks contained | Authorizer is per-connection; any future executor must install it |
| **1c** | `SELECT *` expanded to withheld columns at execution | `SELECT * FROM canvases` returned `tenant_id`/`share_token` | Result-column check before fetch + authorizer | `TestWildcardExpansion` (2 tests) | Withheld columns never returned | `SELECT *` is now refused outright for tables with withheld columns — the model must name columns |
| **1d** | Timeout ended the caller's wait but not the DB work | `tests/test_app_db_execution_boundary.py::TestTimeoutStopsDatabaseWork` — 500M-row recursive CTE aborts inside the budget | In-engine progress-handler deadline + `Connection.interrupt()` from the timeout path | same | Query aborts at ~timeout, not at query completion | Abort granularity is the progress-handler step (1000 VM ops) |
| **1e** | `WITH … SELECT` refused as "not a SELECT" (false negative) | `validate_app_db_sql("WITH x AS (…) SELECT …")` → rejected | `_SELECT_ONLY_RE` accepts `with`; CTE names excluded from the allowlist walk | `TestLegitimateQueriesUnchanged` | CTE + count + join all work | — |
| **1f** | Single-install semantics (no scope filter) | `test_no_scope_filter_is_injected` — row with `tenant_id NULL` survives | unchanged (deliberate) | same | No row dropped | — |
| **2a** | Every `satisfaction ≤ 0.15` counted as fabrication | 0.0 = provider exception, 0.1 = empty content, 0.1 = empty truncation | Bench now requires explicit verdict provenance (`_is_fabrication_verdict`) | `TestVerdictProvenanceSeparation` (5) | Availability/latency rows cannot be benched | — |
| **2b** | **Live table carries no provenance at all** | `router_evidence_report.py`: **0 of 170 rows** have a `verdict` key | verdict written via `prompt_features` | — | — | Until the backend restarts on the new code and writes fresh rows, the bench's numerator is empty in production |
| **2c** | **Corrective signal double-counts one generation** | One `record_fabrication_signal` produced **2** `_persist_feedback` calls (`{'verdict': …}` then `None`); live DB: 2 identical rows share `routing_result_id ad1fa3e1-…` | **FIXED here**: the verdict is stamped on `feedback._prompt_features` so `record_feedback`'s own write carries it; the manual pre-persist runs only on the flag-off path (no router) | verified both paths write exactly **1** row with the verdict; `tests/test_fabrication_bench.py` 22 passed | one verdict → one row, provenance intact | — |
| **3** | "~90 verdict rows" read as a trust basis | `scripts/router_evidence_report.py` → `docs/audits/2026-09-16_router_evidence_reconciliation.md` | Evidence reconciled; trust horizon gated on an executed comparison | script + doc | 170 rows / 168 generations / 4 models / 14.2 h window | Observational only: unexecuted alternatives have no outcome; no candidate-order log persists |
| **4** | "Pasted/quoted text is mail" too broad | `tests/test_planner_natural_routing.py`, `tests/test_verbatim_evidence_generalization.py`, `tests/test_attachment_evidence_general.py` | Provenance-first routing (concurrent session) | 103 tests pass across the 4 suites | Provenance beats wording; own-inventory wording retained | Not re-derived here; verification was suite-level, not a fresh adversarial corpus |
| **5a** | Provider reliability unmeasured | `scripts/provider_reliability_replay.py --topology-only` + the concurrent session's bounded live run (`scripts/provider_reliability_20260916_1248.json`) | Harness + executed snapshot | 6 attempts, 6 ok | **All 9 ranked candidates come from ONE provider (`openrouter`)** | Sample is 6 attempts, not a workload distribution |
| **5b** | **Fallbacks share the failing upstream** | topology output: `fallbacks_share_primary_upstream: true`; the replay's observed models (`qwen/qwen3.8-flash`, `deepseek/deepseek-v4-flash-0731`) are both `openrouter` | **CONFIRMED, not fixed** | — | Primary and all 3 fallbacks are `openrouter` | Capacity purchase is not the first remedy — see §3 |
| **5c** | **Configured independent capacity was unreachable** | `BYOKHandler.clients == ['ollama','openrouter']`; `get_api_key('deepseek') → None`, `('opencode-go') → None` while all 5 keys in `data/byok_keys.json` are tenant-prefixed (`tenant_default_<provider>_<name>_production`) and the lookup built `<provider>_<name>_production` | **FIXED, then CORRECTED.** This session's first fix matched by `(provider, key_name, environment)` fields — which ignored the scope encoded in the id. An independent review (`scripts/redteam_byok_scope_resolution.py`) reproduced **6 cases where that resolver returned a credential the correct contract refuses or reassigns**, including a tenant receiving the operator's global key and an unscoped lookup receiving a tenant's key. The correction resolves by `(scope, provider, name, env)` and **refuses (returns None) when multiple scopes exist with no global entry** | `tests/test_byok_key_store_resolution.py` (34: this session's 8 + the reviewer's collision/precedence/inactive/decryption/round-trip classes); red-team 9/9 contained | All three providers resolve on the live store (single scope, so the ambiguity path cannot trigger today); **routing ladder 9 candidates/1 provider → 118 candidates/3 providers** | The first fallback still shares the primary's provider; two independent providers follow it. The **running backend (pid 89233) predates the correction** — it holds the intermediate resolver, which is outcome-identical for this single-scope store but must not be left in place for a multi-scope one |
| **6a** | Budget trim could drop the decisive row/formulas | `TestBudgetPreservesDecisiveLines` | `_is_decisive` keeps FORMULAS/SQL RESULT/`R###`/figure lines | that test | Decisive lines survive a 1500-char budget | Char budget, not token budget |
| **6b** | Audit claim "headers/SQL/formulas always survive" | contradicted at HEAD before the fix | corrected in the audit | — | — | — |
| **6c** | Total input tokens (history+canvas+instructions+evidence) and per-model output reservation | measured with `core/llm/prompt_budget.py` | **NEW module + measurement** (below) | `tests/test_prompt_budget_accounting.py` (11) | Same 18k chars cost **4,510–8,208 tokens** depending on content shape | Not yet wired into the orchestrator: the evidence budget is applied *before* model selection, so the account is advisory today |
| **6d** | Answer outside the auto-open head/tail window | premise pinned by `test_head_tail_would_have_missed_it` | **FIXED**: `relevant_window` centres the opened window on the query's own terms; the header states the window is targeted, or states explicitly that **no** question term appears (so a head/tail view is never presented as a full read) | `tests/test_auto_open_relevant_window.py` (5) | Mid-document decisive row surfaced where head/tail missed it; miss is stated | Window size is still char-bounded, not token-bounded |
| **7a** | Cache returned by reference; consumers could corrupt it | 3 failing tests in `tests/test_sheet_probe_cache_boundaries.py` | deep copy on store and on hit | 7 tests | Mutation no longer corrupts the cache | — |
| **7b** | Identity-less rows collided; same bytes under different sources shared an entry | 2 failing tests (same file) | identity = `(content_hash, external_id, parquet_path, file_name)`; anonymous entries bypass the cache | same | Content-version invalidation preserved; cross-source identity isolated | — |
| **7c** | `.doc` reported as `no_text` (indistinguishable from empty) | `tests/test_legacy_doc_ingestion_boundary.py` — 4 failing tests | `LEGACY_BINARY_OFFICE_EXTS` → explicit `unsupported_format` + `extraction_supported: False` | 6 tests | Filename discovery ≠ extracted content; renamed `.docx` still parses | `.doc`/`.ppt` extraction itself remains unsupported (separate capability task) |
| **7d** | Office-file per-user ownership | `api/office_routes.py` router-level `Depends(get_current_user)`; `_validate_office_path` takes only `file_path` | **RESOLVED (documented, not migrated)** — see §4b | `tests/test_office_file_ownership_boundary.py` (7, characterization) | Authenticated surface + path containment hold; ownership is **not** enforced | Flat `ATOM_OFFICE_DIR` namespace: any authenticated user may name any office file. Per-user subtrees are a migration because canvas rows persist these paths |
| **8** | Closing evidence + audit corrections | this document | audit §5 updated | — | — | — |

---

## 1. Item 1 — the boundary that mattered

The static-inspection concern was that quoted table names slip past the
extraction regex. That specific framing was **half right**: `SELECT * FROM
"users"` was already caught (the regex skips the quote and matches the bare
name). The real openings were `'users'` (single quotes) and a subquery aliased
to an allowlisted name. After the concurrent session's sqlparse fix, 4 of 15
attacks still passed validation — and **two of them still returned rows**,
because both the validator and the result-column check are blind to a table
read that is never projected:

```sql
SELECT id FROM canvases WHERE (SELECT count(*) FROM 'users') > 0
SELECT id FROM canvases WHERE EXISTS (SELECT 1 FROM (SELECT * FROM 'user_sessions') canvases)
```

That is a 1-bit oracle over any table in the database. The correction is a
SQLite authorizer, which SQLite invokes for every table and column access
after name resolution — covering quoted identifiers, nested subqueries,
wildcard expansion and predicate-only reads uniformly. Verified: 15/15 direct
attacks and 5/5 inference attacks contained, with CTE/count/join queries and
the no-scope-filter single-install semantics intact.

## 2. Item 3 — what the router evidence licenses

Reproduce: `cd backend && ./venv/bin/python scripts/router_evidence_report.py --db data/atom.db`

- 170 rows / **168 distinct generations** / 4 models / a **14.2-hour** window.
- **2 generations were written twice** — one is a primary+fallback pair (each
  row correctly naming the model that produced output), the other a pure
  duplicate.
- **67 rows (39.4%) carry no prompt features**, so they train on task-default
  features.
- **0 of 170 rows carry any verdict provenance**, so the fabrication bench's
  newest rule has nothing to match in production yet.
- Auto-activation's 30-row rule is satisfied — which demonstrates **readiness,
  not superiority**. The audit's "~90 verdict rows" was a moving snapshot of
  one incident's traffic, taken after accrual had been dead since `9a4a2a774`
  and after 8 synthetic `probe/*` rows had been purged.
- A time-ordered holdout (118/52) puts `deepseek-v4-flash` top under **both**
  the learned order and static cost-priority, at ~9.6 s and ~7× lower cost per
  answer than glm. The orders disagree only in ranks 2–3 — and the
  disagreement is **not** a result: the holdout contains only outcomes of the
  model that was actually executed. An unexecuted alternative is recorded as
  `unobserved`, never as a win.

## 3. Item 5 — the capacity question was premature, and the fix is measured

`scripts/provider_reliability_replay.py --topology-only` showed the live ladder:

```
BEFORE  — 9 ranked candidates, providers: {'openrouter': 9}
          fallbacks: openrouter × 3   →  fallbacks_share_primary_upstream: True
```

**Every fallback shared the primary's upstream**, which is the mechanical
reason a 429 storm exhausts both the primary and its fallbacks.

The cause was not capacity. `BYOKHandler` held clients for
`['ollama', 'openrouter']` only, and **every one of the 5 keys in
`data/byok_keys.json` is tenant-prefixed** (`tenant_default_<provider>_<name>_production`)
while `get_api_key` built the unprefixed `<provider>_<name>_production`. The
whole local key store was therefore unreachable at runtime; `openrouter`
survived only because `OPENROUTER_API_KEY` also happened to be in the
environment. `deepseek` and `opencode-go` had no env fallback, so they never
became clients. This also means any key saved through the UI was silently
ignored after a restart.

Fixed in `BYOKManager._find_stored_key` — resolve by fields, not by id shape —
and then **corrected again**, because the first version of that fix was itself
unsafe: matching on `(provider, key_name, environment)` alone ignored the
scope encoded in the entry's id, so it could hand a tenant the operator's
global key, or hand every caller a tenant's key, purely on dict order. An
independent review reproduced six such cases
(`scripts/redteam_byok_scope_resolution.py`). The corrected contract resolves
by `(scope, provider, name, env)` and **refuses when more than one scope
exists with no global entry**, rather than picking the first match. This is
recorded here because it is the clearest evidence that the verification loop
has to run in both directions: a fix can introduce a worse defect than the one
it closes, and only an adversarial reader catches it.

Measured effect on the same live configuration:

```
AFTER   — 118 ranked candidates, providers:
            {'deepseek': 104, 'openrouter': 9, 'opencode-go': 5}
          primary:  opencode-go / gpt-5.3-codex-spark
          fallbacks: opencode-go / gemini-3-flash
                     openrouter  / z-ai/glm-5.3-flash
                     deepseek    / deepseek-reasoner
```

Independent provider diversity exists now; it did not before. The remaining
nuance is that the *first* fallback still shares the primary's provider — two
independent providers follow it, so a single-upstream failure is survivable,
but a future improvement is to order the ladder so the first fallback is
always a different provider.

**Executed:** a bounded 6-attempt live replay
(`backend/scripts/provider_reliability_20260916_1248.json`, 2026-09-16
12:48 UTC): **6/6 ok, 0 zero-visible, 0 rate-limited**, median latency 12.5 s,
max 25.7 s, median time-to-first-visible 13.4 s. Planning calls used
`qwen/qwen3.8-flash` (5.1 s) and `deepseek/deepseek-v4-flash-0731` (12.5 s) —
**both `openrouter`**, which is the topology finding showing up in the
observed data. The two immediately preceding runs (12:46, 12:47) failed 6/6 on
the harness's own defects (`AttributeError: 'BYOKHandler' object has no
attribute 'generate_completion'`, `NameError: name 'svc' is not defined`,
`ImportError: cannot import name 'get_fallback_models'`) — see §4.

This snapshot does not show a congested provider; it shows a **healthy but
single-sourced** one. It therefore cannot by itself justify a capacity
purchase, and it is too small (6 attempts) to characterise a workload.

Presenting capacity purchase as a measured option therefore means, in order:
(1) ~~fix the credential resolution so the configured providers enter the
ladder~~ **done — 3 providers now in the ladder**; (2) re-run the bounded
replay against the now-diverse ladder (the 6-attempt snapshot above predates
the fix and reflects single-provider routing); (3) only if `rate_limited` +
`timeout` remain material at the real prompt size *and* the ladder still shows
insufficient provider diversity, price dedicated capacity against its measured
benefit.

## 3b. Item 6c — what 18,000 characters actually cost

`core/llm/prompt_budget.py` counts every section of the assembled prompt
(instructions + history + canvas + evidence) with a real tokenizer
(`tiktoken`, cl100k_base), reads the provider's context cap, and reserves the
completion budget. Measured on three representative evidence shapes, each cut
to the documented 18,000-character budget:

| evidence shape | chars | tokens | vs char/4 |
|---|---|---|---|
| prose-heavy mailbox lines | 17,794 | **4,510** | 1.01× |
| row-dense (R### price rows) | 17,928 | **7,128** | 1.59× |
| formula-dense (`G235==F235*0.9`) | 17,928 | **8,208** | 1.83× |

The same character budget is a **1.8× different token budget** depending on
content. The char/4 rule of thumb understates numeric and formula-dense
evidence by up to 83% — and that is precisely the content this incident was
about. A character budget is therefore not a context bound, which is what the
audit suspected when it called 18k "measured, not derived".

With the full prompt (8,370 input tokens at the row-dense size) plus the 6,000
token completion reservation, every currently-configured provider still fits:

| provider | window | source | fits |
|---|---|---|---|
| `openrouter` | 200,000 | configured | yes |
| `opencode-go` | 200,000 | configured | yes |
| `deepseek` | 32,000 | **fallback (no `max_context` configured)** | yes |

The `deepseek` fallback is conservative — its real window is larger — but it
only entered the ladder with the item-5c fix, so its limits were never
configured. Until they are, its prompts are budgeted against 32k rather than
its true window.

**Not done:** wiring the account into the orchestrator. The evidence budget is
applied *before* model selection (routing happens later), so enforcement needs
either a post-routing re-check or a two-pass assembly. The module is the
measurement layer that makes that decision possible; it is deliberately
advisory today.

## 4. First-attempt reliability

The audit's own headline number needs the same treatment it demands of the
router: report first attempts separately from retries.

| Signal | Observation |
|---|---|
| Live routing outcomes | glm-5.3-flash 99/99 success, **96%** quality-satisfied; deepseek 35/35; qwen 34/34; gemini 2/2 |
| Retries observed | **1** primary→fallback pair in 168 generations (glm failed, qwen answered in 13.8 s) |
| Duplicate writes | 2 of 168 generations (1.2%) |
| Live reliability replay | **3 harness runs to get 1 valid**: runs 1 and 2 returned 6/6 exceptions from the measurement script's own bugs; run 3 returned 6/6 ok. The published snapshot is a third-attempt success, and is labelled as such here |
| This session's own first attempts | 5 of 9 new executable artifacts needed a correction after their first run (3 report-script defects, 2 test-harness defects) — each found by running, not by reading |
| This session's own production fix | The 5c credential-resolution fix **shipped a cross-tenant credential leak on its first attempt** and was caught by an independent reviewer's red-team, not by the 8 tests written alongside it (those all passed). Corrected in place. A fix's own tests are not evidence that the fix is safe |

The honest summary is that the *platform's* first-attempt reliability on this
traffic is high, and that its retry rate is nearly zero — which is precisely
why a single-upstream ladder is dangerous: with no independent fallback and a
1-in-168 retry rate, a provider-wide incident has no second chance.

## 4b. Item 7d — office-file ownership: what actually holds

Two properties are often conflated; only the first is enforced today.

1. **Containment (enforced).** `_validate_office_path` resolves the path and
   requires it under `ATOM_OFFICE_DIR`. Traversal, symlink escape and the
   `/office-evil` sibling-prefix case are all rejected.
2. **Ownership (NOT enforced).** The validator has no owner parameter and the
   base directory is one flat namespace. Any authenticated user may name any
   office file, because the only authorization gate is
   `router = APIRouter(dependencies=[Depends(get_current_user)])` — i.e.
   *authenticated* means *install-wide access*.

Single-tenancy settles which **install** owns the data. It does not settle
which **user** may read it, and this app has a `User` model with per-user
canvases and `current_user.id` already threaded into `/present` and
`/sync-update`. So the flat namespace is a genuine per-user exposure in a
multi-user install, not a non-issue.

It is **not migrated here** for a concrete reason: office file paths are
persisted on canvas rows (`content.office_file`) and in `CanvasAudit` history,
so introducing `ATOM_OFFICE_DIR/<user_id>/` invalidates existing paths and
needs a backfill plus a compatibility read for legacy rows. That is a scoped
change with its own migration, not a validator tweak — and doing it silently
alongside a verification pass is exactly the kind of unannounced behaviour
change this audit exists to stop.

`tests/test_office_file_ownership_boundary.py` pins both properties, including
the negative one, so the migration flips an assertion deliberately.

## 5. Corrections to the incident audit

1. **§3 "headers/SQL/formulas always surviving"** — false at the time of
   writing: `SQL RESULT` and `FORMULAS` lines were classified as elidable body
   lines. Corrected by `_is_decisive`; pinned by
   `TestBudgetPreservesDecisiveLines`.
2. **§5.4 "~90 verdict rows"** — not a representative sample. Accrual was dead
   from `9a4a2a774` until `76cc51bcd`; every row postdates 2026-09-15 22:24
   UTC. Replaced with the reconciliation report.
3. **§2.5 RC-18 "a completed app-DB NL→SQL with a table allowlist"** — the
   allowlist was not, by itself, a boundary. See item 1.
4. **§5.1 "this is an infrastructure spend decision, not a code fix"** —
   contradicted by measurement: the ladder has one provider because two
   configured providers are unreachable, which is a code fix.
5. **§5.2 legacy `.doc`** — now bounded: the file remains name-only, but the
   result says so explicitly instead of reporting `no_text`.
6. **§4 "220+ tests"** — one of them (`TestNLSQLLayerWiring`) had been left
   green-by-arity: its fake accepted 6 positional arguments while production
   passed 8, so every real argument became a `TypeError` swallowed into a
   "returned nothing" result. Re-contracted to pin behaviour, not arity.

## 5b. Live verification, and a stale-server trap

The backend was restarted (pid 89233) and the code changes verified on the
running process from its startup log:

```
INFO:core.llm.byok_handler:Initialized deepseek client using BYOK credential
INFO:core.llm.byok_handler:Initialized openrouter client using BYOK credential
INFO:core.llm.byok_handler:Initialized opencode-go client using BYOK credential
```

Before the 5c fix only `openrouter` (plus local `ollama`) were configured.

**But the restart exposed a trap that affects every live claim in the
incident record.** Two servers were listening:

| port | pid | started | code |
|---|---|---|---|
| 8000 | 87171 | **Sep 6** | ~10 days stale — none of this week's fixes |
| 8001 | 89233 | Sep 16 09:17 | current (`scripts/restart_backend.sh` manages this one) |

`scripts/restart_backend.sh` restarts **8001**, while an older process has
held **8000** since September 6. Any HTTP probe aimed at the default port was
answered by ten-day-old code. This does not invalidate the log/payload-based
root causes (they were captured from the process serving the turns), but it
does mean:

- live-verification claims must name the port they were made against;
- `llm_routing_feedback` rows written during the incident may have come from
  either process;
- the "restart the backend, then re-verify" instruction needs an explicit
  port, or the stale listener killed first.

This is the same class of error the audit already names ("testing against a
stale server produces false bug reports"), one process older.

## 6. Open items (explicitly not done)

> **Superseded 2026-09-16 (round 2)** by
> [`2026-09-16_gap_closure_matrix.md`](2026-09-16_gap_closure_matrix.md), which
> separates **implemented** / **isolated verification passed** / **live
> verification passed**, with the tested revision (`a3aa31ba4`) and the
> effective configuration read from the running process. Closed since this
> table was written: the evidence budget is a hard bound (not merely "decisive
> lines survive"); the complete prompt IS accounted against the selected
> model's window minus its output reservation; and the app-DB SQL boundary plus
> the verdict lifecycle are verified through an isolated public-API instance on
> a scratch database (`scripts/verify_isolated_api_boundary.py`, 14/14).

| Item | Why it is open |
|---|---|
| Fix the corrective-signal double-write (2c) | **Done** — see matrix row 2c |
| Fix BYOK provider resolution (5c) | **Done** — see matrix row 5c |
| Wire the token account into prompt assembly (6c) | Measurement layer is done; enforcement must happen after routing, or via a two-pass assembly |
| Configure `deepseek` `max_context` | It entered the ladder with the 5c fix and is currently budgeted against the 32k fallback |
| Token-bound (rather than char-bound) auto-open windows | `relevant_window` takes a char budget; `prompt_budget.count_tokens` could size it per model |
| `.doc`/`.ppt` extraction | Separate capability task via LibreOffice headless (`core.workbook_runtime._find_soffice` is the existing discovery helper) |
| Per-user office-file subtrees (7d) | Ownership boundary resolved and pinned, but the migration is deliberately not bundled here: persisted canvas paths need a backfill. See §4b |
