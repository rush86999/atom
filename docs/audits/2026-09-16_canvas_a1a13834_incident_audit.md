# External Audit Report — Canvas a1a13834 Incident Family

**Period:** 2026-09-13 → 2026-09-16 · **System:** ATOM agent platform
(chat orchestrator, tool planner, evidence pipeline, LLM routing)
**Scope:** one user-visible failure ("search for this one: $ 5,350.00 - 10 %
in stock" misrouted, then reported as a timeout) that exposed a deep stack
of latent defects across 7 subsystems. All root causes listed below were
reproduced from runtime evidence (logs, payloads, live API probes) before
fixing, and each fix was verified live end-to-end or by red-first tests.
**Commits:** 40+ scoped commits (index at the end); tests grew from ~50 to
220+ across the affected suites.

---

## 1. The problem, as the user experienced it

On an open email-canvas (a quotation draft), the user pasted a line from a
vendor email and asked the agent to find it. Over two dozen follow-up
turns across four days, the agent:

1. Routed the pasted quote line to **Zoho Inventory** (because it contained
   the word "stock") and reported a "timeout" — the lookup had actually
   failed with an HTTP 400 and never ran a second attempt.
2. Failed to find emails by their actual attributes (sender, recipient,
   stated date, attachment names), attributing a supplier-bound email to
   the user and miscounting results.
3. Fabricated a price derivation ("+10% add-back, ÷0.70, +$473 Google-review
   markup") exactly fitting the user's own hypothesis, while the true
   calculation sat fully ingested in a workbook the whole time.
4. Repeatedly answered "the lookup didn't run / try again" on identical
   retries, with no fresh evidence despite the store holding the answers.

Each behavior was honest-sounding; none was truthful. The audit trail
below shows every one traced to a specific mechanical defect, not to
model randomness.

## 2. Root causes found (each reproduced before fixing)

### 2.1 Provider-API layer
- **RC-1 Query construction.** The planner's identifier-enrichment net
  appended a brennan.ca product-URL *path* as a "product token," producing
  a 126-char search value. Zoho rejects values ≥100 chars with HTTP 400
  code 15 — validated **before authentication** (verified live: an invalid
  bearer receives the same code-15 first), so the failure masqueraded as
  an integration problem.
- **RC-2 Ladder abort.** The shared provider-search ladder
  (`run_search_ladder`) failed fast on the first attempt's error, so a
  value-specific 400 killed rungs (per-token searches) that would have
  succeeded.
- **RC-3 Tokenization.** Hyphenated catalog codes (`F-5216`) were split by
  the tokenizer; the code never received its own search rung.

### 2.2 Routing layer (which tool, which data)
- **RC-4 Context-blind planner.** The tool planner received one line of
  message text — not the open canvas, not which ingested store already
  contained the quoted text, not whose data each app holds.
- **RC-5 Keyword-overlap routing.** "in stock" matched the inventory
  catalog description; no whose-data semantics distinguished the user's
  own records from correspondence others sent them.
- **RC-6 A pasted quote line is mail.** No rule established that quoted
  text is a stored message to be found, not a catalog query.

### 2.3 Evidence layer (what the reply model sees)
- **RC-7 Partial coverage.** Deterministic evidence (figures, quoted
  phrases, participant names) only ran on some plan outcomes; declined
  plans — the common case for follow-up turns — injected nothing, and the
  model narrated from ambient memory (fabricating recipient attribution).
- **RC-8 Misleading failure copy.** The failure-injection block's wording
  let replies *open* with the failure ("the live lookup did not
  complete…") while the answer sat in the same prompt.
- **RC-9 Starved evidence legs.** The ingested-mail store cache TTL was
  5 seconds against a ~10-second cold reload (7,154 rows, 340MB metadata
  column): nearly every evidence call paid a full reload, and under load
  the reload exceeded the legs' wait windows → empty evidence → "no fresh
  results."
- **RC-10 Long artifacts vs one-shot window.** Full threads (79k chars),
  attachments, and 200-row grids had no bounded projection; evidence size
  was the uncoordinated sum of per-lane caps.

### 2.4 LLM-routing layer (which model, at what consequence)
- **RC-11 No fabrication consequence.** Response-quality scoring had no
  hallucination term; a model could invent prices every turn and keep
  winning routes. `ATOM_LEARNING_ROUTER` was off and manual.
- **RC-12 Cancelled calls taught nothing.** Budget-cancelled planning
  calls (75s canvas-edit plans, live) left no routing feedback — the
  coroutine died before outcome recording — so the router could not learn
  a model was too slow.
- **RC-13 Zero-visible streams.** Reasoning-mandatory models ended with
  `finish_reason=length` and zero visible tokens, consuming whole turn
  budgets; the fallback re-rolled the same model.

### 2.5 Catalog/workbook layer
- **RC-14 Dimension-spelled rows.** The workbook spells the product
  `F-52"x16G`; the code `5216` can never substring-match it — but the
  row's own values (5350, 7519) do.
- **RC-15 Intermittent catalog scans.** Each catalog probe re-scanned
  200+ parquet files per token per turn (3.7s), making answers flaky
  under load.
- **RC-16 No formulas on the deterministic path.** Only the LLM-SQL path
  attached the workbook's formula sidecar; fast answers showed values
  without the derivation.
- **RC-17 Ranking ties.** Scattered common-word matches ("price"+"list")
  tied the *named* file and displaced it; within the winning file, a row
  matching a canvas figure ($8,880) displaced the row the message asked
  about ($7,519).
- **RC-18 Orphaned app-DB primitive.** A schema-aware NL→SQL generator
  existed with zero callers and no table allowlist (raw wiring could have
  selected credential tables).

## 3. The solution architecture

Design rule throughout: **deterministic layers extract and gate; the LLM
decides; deterministic floors correct when evidence contradicts the
choice.** Full design: `docs/architecture/TOOL_PLANNER_ROUTING.md` (§1–8).

1. **Provider ladder hardening** (RC-1..3): value-level 4xx skips the
   rung (transport/auth/5xx still fail fast); hyphenated codes tokenize
   whole; values capped to provider limits.
2. **Provenance-first routing** (RC-4..6): the planner sees the open
   canvas (bounded), a *provenance menu* (which ingested store already
   contains the quoted tokens — resolved before planning), whose-data
   catalog semantics (record apps = your own state; mail = others'
   claims), a pasted-text-is-mail rule, and a narrow obedience floor
   (quote-lookup + verbatim provenance + record-app plan → one repair
   pass → deterministic memory rung). A deterministic send-gate stops
   questions from becoming send proposals.
3. **The evidence compiler** (RC-7..10): one resolution order on every
   plan outcome (figures → quoted phrases → participants → inherited
   figures), stated dates tier matches ("sent 9/11 friday", anaphoric
   "that day"), directionality ("by X"/"to me"), attachment names with
   open paths, a harness-side auto-open of the top cited artifact (the
   one-shot chaining gap), and a single evidence budget
   (`ATOM_EVIDENCE_BUDGET_CHARS`, 18k) with headers/SQL/formulas always
   surviving. Grid canvases project as schema+dimensions+samples.
4. **Safety routing** (RC-11..13): a fabrication term in response quality
   (0.1/0.15, *below* truncation/refusal — invisible lies are worse than
   visible incompleteness); corrective observation from guards attributed
   to the producing model; a **fabrication bench** (≥3 verdicts at ≥25%
   over 48h → excluded from candidates; independent of any flag);
   **learning-router auto-activation** (tri-state `auto`: re-ranking
   self-enables at ≥30 verdict rows / ≥2 models / ≥8 obs each — verified
   live to have self-activated on this incident's own traffic); timeout
   outcomes recorded at cancellation (the router finally learns slowness);
   zero-visible streams yield to a next-ranked pinned fallback with a
   reserved budget window.
5. **Catalog completion** (RC-14..18): figure-value probes with
   co-occurrence ranking; immutable-source freshness (email attachments
   cannot change — a new version is a new message); NL→SQL wired on the
   top-ranked file; formulas attached on the deterministic path; a
   per-(content-version, token) probe cache (3.7s → 0.01s warm);
   filename-phrase dominance and row-level selection (message-figure
   tie-break); and a completed app-DB NL→SQL with a table allowlist,
   secret-column stripping (prompt and parse), SELECT-only, read-only
   execution.

## 4. Verification evidence

- **Live end-to-end** (real backend, real store, real provider): the
  original ask now returns the grounded thread (Joel Seguin, Aug 26,
  $5,350.00 − 10%, Fintek F-5216 spec-sheet attachment); the directional
  ask returns the two forwards with PRICE VIPUL (6).xlsx named; the
  derivation ask returns row 235's exact formula chain with an honesty
  note. Snippets preserved in `notes/AGENT_COORDINATION.md` entries and
  commit messages.
- **Tests:** 220+ passing across the affected suites; every detector
  pinned in both directions (fires / realistic non-fire); re-contracted
  tests documented where behavior intentionally changed.
- **Negative controls:** the comms-cache starvation and the catalog
  intermittency were both reproduced empty before their fixes and full
  after; the derivation trigger's domain-independence pinned with a
  non-commerce case ("reliability score").

## 5. Open items — outside guidance requested

1. **Provider tier reliability (highest impact).** The OpenRouter shared
   pool produced multi-hour 429 storms and reasoning-mandatory
   zero-visible streams on heavy prompts; even with budget reservation
   and pinned fallbacks, both top models can exhaust a turn. Options:
   paid keys/dedicated capacity, a second gateway, or local fallback
   models for planning-class calls. This is an infrastructure spend
   decision, not a code fix.
2. **Legacy `.doc` ingestion.** The Fintek spec sheet (binary `.doc`) is
   name-only in the store; the engine parses docx/xlsx/pdf. Adding `.doc`
   support (LibreOffice headless or similar) is a capability decision.
3. **Evidence budget tuning.** 18k chars is measured, not derived; a
   formal context-usage audit across model tiers would set it
   per-provider.
4. **Learning-router trust horizon.** Re-ranking is now auto-active on
   ~90 verdict rows. How long to run shadow-compare against static BPC
   before trusting it as primary (or whether to require N turns of
   parity) is a policy call.
5. **Known deferred items** (documented, not incident-related): per-user
   ownership inside the office-files directory; Stage-0 probe results
   cached by reference (read-only contract).

## 6. Artifact index

- **Architecture:** `docs/architecture/TOOL_PLANNER_ROUTING.md` §1–8
- **Coordination log (full chronology):** `notes/AGENT_COORDINATION.md`,
  2026-09-13 → 2026-09-16 entries
- **Key commits:** 924b70792 (Zoho 400 chain) → 85a08809e (provenance
  routing) → b5dc3a74b (evidence legs) → 5d2c0d7b9 (send gate) →
  79179a7c5 (reply-leg survival) → e781915f8 (mail-led composer) →
  b50a54c52 (stated dates) → 705d9c8f7 (mentioned_date piggyback) →
  83dd53713 (evidence compiler) → 586a8e6b8 (fabrication bench) →
  9a4a2a774 (router auto) → e49870176 (app-DB NL→SQL) → 732bca823
  (cache TTL) → 82261d974 (timeout outcomes) → 0c5ed07a0 (gap closure)
- **Test batteries:** test_identifier_search, test_zoho_inventory_search,
  test_planner_natural_routing, test_verbatim_evidence_generalization,
  test_canvas_editor_grounding, test_fabrication_bench,
  test_app_db_query, test_attachment_evidence_general

---

## 7. Post-issuance verification round (2026-09-16, external-audit items)

Outside review flagged eight verification/correction priorities; each was
reproduced on isolated fixtures before correction where it alleged a defect.

| # | Issue | Reproduction | Correction | Regression coverage | Boundary verified | Remaining limitation |
|---|---|---|---|---|---|---|
| 1 | App-DB SQL boundary: regex table extraction missed quoted identifiers and comma joins; `SELECT * FROM "users"` passed validation; wildcard bypassed column checks; timeout ended the wait, not the work | Scratch DB with dummy `hashed_password`/`two_factor_secret` — the quoted-table and comma-join forms **leaked secrets at execution**; slow cartesian ignored the caller's expiry | sqlparse token-walk extraction (quoted/comma/subquery); execution-time result-column gate before first fetch (wildcard expansion refuses secret-shaped columns); `set_progress_handler` aborts the query in-engine at the deadline | 6 new tests (4 bypass shapes, execution refusal, in-engine abort at ~deadline) | Read-only ≠ unauthorized-read-free — now enforced at BOTH validation and execution; single-install semantics preserved (refusal or full-table, no silent filters) | JSON1 `json_extract` in generated SQL not separately gated; prompt-injected SQL that stays within allowlisted tables/columns is by-design readable |
| 2 | Fabrication bench conflated verdicts: empty (0.1), empty-truncation (0.1), exceptions (0.0) share the fabrication score band and **benched outage victims as fabricators** (reproduced: 3 empty + 1 clean → benched under old rule) | Failing tests first on scratch rows | Verdict provenance: corrective signals stamp `prompt_features.verdict` (`unsupported_figures`/`ungrounded_claims`/`timeout`); the bench counts ONLY stamped fabrication verdicts (score bound kept as guard) | 6 new tests; 3 re-contracted to the verdict contract | Attribution verified (resolved-model echo at the call site); outcome+corrective pair no longer double-counts for the BENCH (outcome rows unstamped → excluded) | The learning PREDICTOR still sees both rows of a corrective pair — acceptable (continuous signal), documented |
| 3 | "~90 verdict rows" unreconciled; readiness ≠ superiority | Live query: 177 rows/7d, all post-observation-unblocking (22:24 Sep 15 onward), 0 probe residue — consistent with the cleaned persistence failure; glm 99/qwen 38/deepseek 35 rows (3 models ≥8) | Disagreement logging installed: when learned ≠ static ordering, both orders + chosen top are logged, **with an explicit no-outcome marker for the unchosen alternative** | (log-line contract test deferred — INFO-level observability) | Distinct generations cannot be retroactively separated from rows; verdict stamps make corrective rows identifiable going FORWARD | Held-out evaluation vs static BPC now has its evidence stream (the disagreement log); no superiority claim is made |
| 4 | "Pasted text is mail" too broad | Reasoned cases: quotes from workbooks/documents/CRM/web/unidentifiable; own-inventory questions with identical "stock"+price wording | Rule generalized to PROVENANCE-DETERMINED ROUTING (provenance block is the authority; correspondence-like default only when no provenance; genuine own-record questions keep record-app routing) | 4 new tests incl. both-direction quote-shape pins; 1 prompt-contract re-contract | Floor still diverts only quote-lookup-SHAPED record-app plans — plain questions never diverted | Web-sourced quotes rely on planner judgment absent provenance (documented) |
| 5 | Provider spend recommendation lacked measurement | **Measured, bounded run (6 attempts, this window): 6/6 ok, 0 zero-visible, 0 429s, median 12.5s, ttfv 13.4s** — the current window is healthy; earlier storms were real but episodic | Harness delivered (`scripts/measure_provider_reliability.py`, JSON + console) for repeat runs during degradation windows | n/a (measurement) | Congestion vs budget separated by stage/finish-reason fields | 6 attempts is a snapshot, not a distribution — run N≥20 during the next degradation window BEFORE any capacity purchase; no infrastructure claim is made from this snapshot |
| 6 | Budget trim could drop the decisive row; surviving citation ≠ derivation | Forced-small-budget test: prose survived alongside R235/FORMULAS under the old trim in the lucky case | Decisive-line priority: R### rows, FORMULAS, SQL RESULT, and figure-bearing lines trim LAST (prose first) | 1 new test (small budget keeps R235 + formulas, elides prose) | Head/tail out-of-window answers already carry the MATCH-window anchor | Full derivation-completeness metric (units/dates/attribution preservation) not yet automated |
| 7 | Capability bounding | Cache consumers share results by reference (mutation would poison readers — documented contract test); .doc ingestion unsolved; office-file ownership deferred | .doc treated as a separate capability task (filename discovery vs extracted contents already distinct in evidence lines); cache contract pinned | 1 contract test (documents current behavior with the fix-ticket noted) | Content-version invalidation verified (content-hash key); concurrent cold loads untested | Copy-on-return if a mutating consumer appears; ownership per actual access paths still open |
| 8 | Closing discipline | Uncommitted concurrent-session sheet-service/orchestrator work verified (117+74 tests) and landed credited; tracker + coordination checked before shared-file edits | This matrix; audit §5.1 softened — infrastructure is A measured option, not THE remaining cause (item 5's healthy snapshot) | 191 passed across seven suites this round | Live public-API verification after coordinated restart below | — |

**Correction to §5.1 of this report:** the original text recommended provider-tier
spend as the highest-impact item without measurement. The bounded replay shows
the current window healthy (6/6, no zero-visible, no 429s); the honest position
is that degradation is EPISODIC and the delivered harness is the decision
instrument — purchase capacity only against a measured degradation window.
