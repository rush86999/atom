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
| **2c** | **Corrective signal double-counts one generation** | Live DB: 2 identical rows share one `routing_result_id`; `record_fabrication_signal` persists once with the verdict and again via `record_feedback` with `None` | **NOT FIXED** — filed | — | — | One verdict → 2 rows; the duplicate inflates the bench denominator and trains on task-default features |
| **3** | "~90 verdict rows" read as a trust basis | `scripts/router_evidence_report.py` → `docs/audits/2026-09-16_router_evidence_reconciliation.md` | Evidence reconciled; trust horizon gated on an executed comparison | script + doc | 170 rows / 168 generations / 4 models / 14.2 h window | Observational only: unexecuted alternatives have no outcome; no candidate-order log persists |
| **4** | "Pasted/quoted text is mail" too broad | `tests/test_planner_natural_routing.py`, `tests/test_verbatim_evidence_generalization.py`, `tests/test_attachment_evidence_general.py` | Provenance-first routing (concurrent session) | 103 tests pass across the 4 suites | Provenance beats wording; own-inventory wording retained | Not re-derived here; verification was suite-level, not a fresh adversarial corpus |
| **5a** | Provider reliability unmeasured | `scripts/provider_reliability_replay.py --topology-only` | Harness + topology check | script | **All 9 ranked candidates come from ONE provider (`openrouter`)** | Live replay not executed (see §3) |
| **5b** | **Fallbacks share the failing upstream** | topology output: `fallbacks_share_primary_upstream: true` | **CONFIRMED, not fixed** | — | Primary and all 3 fallbacks are `openrouter` | Capacity purchase is not the first remedy — see §3 |
| **5c** | **Configured independent capacity is unreachable** | `BYOKHandler.clients == ['ollama','openrouter']`; `BYOKManager.get_api_key('deepseek') → None`, `('opencode-go') → None` while both keys exist in `data/byok_keys.json` | **NOT FIXED** — filed | — | — | The single-upstream exposure is a credential-resolution defect, not a capacity shortage |
| **6a** | Budget trim could drop the decisive row/formulas | `TestBudgetPreservesDecisiveLines` | `_is_decisive` keeps FORMULAS/SQL RESULT/`R###`/figure lines | that test | Decisive lines survive a 1500-char budget | Char budget, not token budget |
| **6b** | Audit claim "headers/SQL/formulas always survive" | contradicted at HEAD before the fix | corrected in the audit | — | — | — |
| **6c** | Total input tokens (history+canvas+instructions+evidence) and per-model output reservation | not measured | **NOT DONE** — filed | — | — | 18k chars remains a measured-once baseline with no per-provider token accounting |
| **6d** | Answer outside the auto-open head/tail window | `_auto_open_top_citation` takes head 2600 + tail 1200 chars only | **NOT FIXED** — filed | — | — | A mid-document decisive line can still be missing; needs a bounded relevant window or an explicit missing-evidence statement |
| **7a** | Cache returned by reference; consumers could corrupt it | 3 failing tests in `tests/test_sheet_probe_cache_boundaries.py` | deep copy on store and on hit | 7 tests | Mutation no longer corrupts the cache | — |
| **7b** | Identity-less rows collided; same bytes under different sources shared an entry | 2 failing tests (same file) | identity = `(content_hash, external_id, parquet_path, file_name)`; anonymous entries bypass the cache | same | Content-version invalidation preserved; cross-source identity isolated | — |
| **7c** | `.doc` reported as `no_text` (indistinguishable from empty) | `tests/test_legacy_doc_ingestion_boundary.py` — 4 failing tests | `LEGACY_BINARY_OFFICE_EXTS` → explicit `unsupported_format` + `extraction_supported: False` | 6 tests | Filename discovery ≠ extracted content; renamed `.docx` still parses | `.doc`/`.ppt` extraction itself remains unsupported (separate capability task) |
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

## 3. Item 5 — the capacity question is premature

`scripts/provider_reliability_replay.py --topology-only` shows the live ladder:

```
9 ranked candidates — providers: {'openrouter': 9}
primary:  openrouter / z-ai/glm-5.3-flash
fallbacks: openrouter / qwen3.8-flash, openrouter / deepseek-v4-flash-0731,
           openrouter / xiaomi/mimo-v2.5-pro
fallbacks_share_primary_upstream: True
```

**Every fallback shares the primary's upstream.** That is the mechanical reason
a 429 storm exhausts both the primary and its fallbacks.

The remedy is *not* yet a purchase. `BYOKHandler` holds clients for
`['ollama', 'openrouter']` only, and `BYOKManager.get_api_key()` returns
`None` for both `deepseek` and `opencode-go` **although both keys are present
in `data/byok_keys.json`** with `provider_id` values of `deepseek` and
`opencode-go`. Independent, already-configured capacity is therefore
unreachable, which is a credential-resolution defect rather than an
infrastructure shortage.

**Not executed:** the bounded live replay itself. Recording planning success,
grounded-answer success, TTFT, zero-output frequency, rate limits and cost per
successful answer requires generation calls against the user's provider
accounts, and the tree was under active concurrent modification throughout.
The harness is committed and bounded (`--budget-calls`, default 6) and
separates provider congestion from prompt size (three input tiers) and from
turn-budget exhaustion (`budget_exceeded` is its own outcome label).

Presenting capacity purchase as a measured option therefore means, in order:
(1) fix the credential resolution so the two configured providers enter the
ladder; (2) run the bounded replay; (3) only if `rate_limited` + `timeout`
remain material at the real prompt size *and* the ladder still shows no
provider diversity, price dedicated capacity against its measured benefit.

## 4. First-attempt reliability

The audit's own headline number needs the same treatment it demands of the
router: report first attempts separately from retries.

| Signal | Observation |
|---|---|
| Live routing outcomes | glm-5.3-flash 99/99 success, **96%** quality-satisfied; deepseek 35/35; qwen 34/34; gemini 2/2 |
| Retries observed | **1** primary→fallback pair in 168 generations (glm failed, qwen answered in 13.8 s) |
| Duplicate writes | 2 of 168 generations (1.2%) |
| This session's own first attempts | 5 of 9 new executable artifacts needed a correction after their first run (3 report-script defects, 2 test-harness defects) — each found by running, not by reading |

The honest summary is that the *platform's* first-attempt reliability on this
traffic is high, and that its retry rate is nearly zero — which is precisely
why a single-upstream ladder is dangerous: with no independent fallback and a
1-in-168 retry rate, a provider-wide incident has no second chance.

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

## 6. Open items (explicitly not done)

| Item | Why it is open |
|---|---|
| Fix the corrective-signal double-write (2c) | `learning_router_registry.py` / `byok_handler.py` were under active concurrent edit; the fix (carry the verdict on the feedback object, drop the manual pre-persist) needs a quiet tree |
| Fix BYOK provider resolution (5c) | Credential-resolution path is security-sensitive and shared; filed with exact reproduction |
| Total input-token accounting and per-model output reservation (6c) | Requires per-provider tokenizer work; 18k chars remains the baseline |
| Relevant-window auto-open instead of head/tail (6d) | Needs a token-scored window over the cited artifact |
| `.doc`/`.ppt` extraction | Separate capability task via LibreOffice headless (`core.workbook_runtime._find_soffice` is the existing discovery helper) |
| Office-file per-user ownership | Not re-derived here; the cache work confirms scope isolation is now key-based, but office-file authorization paths were outside this session's reproduction |
