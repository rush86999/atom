# Acceptance Baseline — Manifest and Procedures (isolated)

Frozen at revision `39d6532d5af3edbd51c4abec2c3f98ab026cf13b` (2026-09-25).
Files here are the frozen acceptance baseline for the finalization migration
(03_FINALIZATION_SPEC). Modification rule: any change requires a dated delta
entry in ../00_BASELINE.md §5; expected outcomes are never edited to make a
run pass.

## 1. Fixture inventory (all hash-pinned in `fixtures/SHA256SUMS`)

| Fixture | Content |
|---|---|
| `fixtures/conversation_original_drift.json` | THE original panel conversation (session replay-retry2-20260923, 65 messages, incl. pending-file state in metadata) — verbatim user turns: the drift sequence, the canvas rebuild turns, the quote figures in the user's own words |
| `fixtures/conversation_quote_thread.json` | Sept 18/22 quote thread (session bd04ff7f-…) — quote evidence |
| `fixtures/conversation_email_prices.json` | Email price-search session (fleet-probe2-20260922) |
| `fixtures/conversation_true_eight_replay.json` | Verified TRUE-EIGHT replay (session wb-original8-20260925) |
| `fixtures/conversation_inherit_verify.json` | Identifier-inheritance verification session |
| `fixtures/canvas_incident_quote.json` | Incident canvas 0e4defa5… ("Quote – Roper Whitney Roll Bender…") + all 12 canvas_audit rows |
| `fixtures/dataset_entries_workbook.json` | All 46 dataset_entries rows for content_hash ff2597d26fc6… |
| `fixtures/workbook_sheet_datasets_ff2597d26fc6/` | The 46 workbook parquet sheets (1.8M) — the indexed source snapshot |

## 2. Isolated run procedure (NO live lane, NO mutable shared data)

The harness `backend/scripts/orchestration_acceptance/run_isolated.py`
implements this end to end:

1. **Build the scratch world** (default under `backend/data/acceptance_worlds/<name>/`,
   gitignored): consistent snapshot of the live DB taken via the SQLite
   online-backup API from a read-only connection (`world/data/atom.db`;
   its sha256 is recorded in `world/MANIFEST.json` at build time — the
   snapshot is a frozen input once built); the 46 workbook parquets are
   copied from the FIXTURES dir (hash-verified), and `dataset_entries.parquet_path`
   rows are rewritten to the scratch world so no run ever reads or writes
   the live sheet-datasets store.
2. **Launch the isolated server**: `uvicorn main_api_app:app` on a dedicated
   port (default 8021) with `DATABASE_URL` = absolute scratch path (the app
   loads `.env` with override=False, so the exported value wins — verified),
   `ATOM_DATA_DIR` = scratch data dir, `LANCEDB_URI` = scratch (fresh, empty
   memory store — deterministic; recorded in the run report).
3. **Run cases** from `cases.json` at the declared sample counts against the
   isolated server only.
4. **Record** per-run: four-dimension outcomes, per-target comparison vs
   frozen expectations, claim-check results, and latencies per the metric
   definitions in `thresholds.json` (progress-event vs first validated
   answer text vs total; HTTP-only runs record turn totals and mark the
   split metrics as not-yet-instrumented).
5. Apply `thresholds.json` pass rules. Results go to `results/`.

**Old-path capture**: same procedure, old path, until
`samples_per_llm_case_min` (20) is reached for latency percentiles; write
`metrics_old_path.json` (schema below). Authority is blocked while it is
incomplete.

```json
{"captured_at": "<iso>", "revision": "<hash>", "config": "runtime_config.env",
 "cases": [{"case_id": "...", "samples": [{"run": 1, "correct_completion": true,
   "unsupported_claims": 0, "unnecessary_clarification": false,
   "progress_event_latency_s": null, "first_validated_answer_text_s": null,
   "total_s": 0.0, "cost_usd": 0.0}]}]}
```

## 3. Live connector smoke test (SEPARATE — not part of the baseline)

Authorized one-off checks that need real connectors (Zoho fetch freshness,
email retrieval) may run against the live lane under the existing
coordination protocol, but they are NEVER acceptance evidence and never
mixed into `results/`. Reproducible acceptance evidence comes only from the
isolated procedure above.

## 4. Isolation model (v3 — review round 5, 2026-09-25)

Everything in v2, plus:

- **The EXTRACTED files are verified, not just the archive stream**: the
  export tree is manifested file-by-file (`world/code_manifest.json`,
  archive-derived) and preflight re-hashes the actual `world/code` tree
  against it — post-extraction tampering or extra files abort the run. The
  tree is chmod read-only and the server runs with
  `PYTHONDONTWRITEBYTECODE=1` so the runtime itself cannot modify it.
- **The network claim is precise and proven**: external connections are
  BLOCKED; loopback is restricted to the TEST SERVER'S OWN PORT (no access
  to other local services, including the live backend on :8001). The
  boundary is proven empirically at world build (loopback probe connects,
  external probe refused) and the proof is recorded + asserted at preflight.
- **Complete provenance for every priced target**: each expected finding
  freezes sheet + target cell + value column + row + basis (e.g. U-22 →
  `linmac!A26`, value col `C`, basis `List Price`, 1777.0). Citation cells
  come from the deterministic renderer at the pinned revision; sheet,
  label, price column, basis, and value are verified against the frozen
  parquets (`provenance_rule` in cases.json). A priced expectation WITHOUT
  frozen provenance is rejected by the evaluator.
- **Contradictory duplicate rows fail** (`contradictory_rows`), never
  silently first-wins; identical duplicates are tolerated. Sixteen negative
  self-tests pin all of this (`--selftest`).
- Gate version: `enforced-isolation-v3`.

## 5. Run records (2026-09-25)

- Runs 1–2 `smoke-pre-enforcement`, runs 3–4 `enforced-isolation` (v1),
  run 5 `enforced-isolation-v2`: preserved under their labels, EXCLUDED
  from the gate.
- **v3.0 gated collection**: 20/20 primary-case samples (see rev 6 delta).
- **v3.1 additions (claim correctness + new cases, SUPERSEDED evaluator)**:
  - **Claim-correctness evaluator** now runs independently of target
    correctness over the ENTIRE response (mutation / freshness /
    completion / absence-scope assertions). Its first regrade of the 20
    saved v3.0 runs exposed a false positive — the HONEST disclosure
    sentence ("NOT a fresh read of the live file") matched the freshness
    pattern — fixed with a disclosure/negation exemption and pinned by
    self-tests; after the fix all 25 saved runs regrade to 0 unsupported
    (excerpt-limited; v3.0 runs persisted 1500-char excerpts, v3.1 runs
    persist full replies). `unsupported_claims` is `null` (unmeasured)
    wherever no evaluator ran — never zero by default.
  - **New cases collected (3 samples each, all passing, claims measured,
    zero unsupported)**: `partial_failure_absent_targets` (honest scoped
    absence, no fabricated values); `planner_down_no_apply` (the live
    2026-09-25 false-edit-claim defect class: no mutation performed, no
    edit claim in the reply); `overlap_concurrent_reads` (two concurrent
    asks on one session — verified distinct execution ids per turn, each
    reply correct for its own ask; READ-READ overlap only).
  - **WS measurements**: progress-event latency 0.01–0.39s captured on
    tapped primary-case samples; no `chat_token` events fire on the
    deterministic lane (it does not stream tokens), so first-answer-text
    latency for narration lanes remains unmeasured pending the
    recorded-response rig.
- **Totals**: 32 gated runs, all passing, zero measured unsupported claims.

- **v3.2 (review round 7 — metric renamed and record-calibrated)**:
  - The claim metric is now **"unsupported claims detected by rule set v2"**:
    a CLOSED pattern vocabulary with a closed verb→kind map, calibrated
    against the turn's TRACE RECORDS (performed action kinds) and the case's
    FROZEN source facts (from the fixture dataset registry — never inferred
    from the reply's wording). Coverage beyond the ruleset is unmeasured by
    declaration; it is not extended by accreting verbs.
  - Exemption tightening: negation counts only directly before the
    qualifier (both "NOT a fresh read of the live file" and "prices are not
    current" are clean; "current prices" inside a materialized-copy
    sentence still flags; a distant "not" exempts nothing). First-person
    action claims require subject–verb adjacency, so negation is handled
    structurally. 29 self-tests including the review counterexamples
    ("I sent the email" with no send record; record-backed "I sent the
    email" clean).
  - **Claim gate eligibility**: only full-response, ruleset-v2,
    record-calibrated runs count (`counts_toward_claim_gate`); the 23
    earlier v3.0/v3.1 runs (excerpt-only or reply-derived source status)
    keep target and latency gating but are claim-UNMEASURED.
  - **Answer availability** measured at HTTP response receipt
    (`answer_availability_latency_s`, with basis note) — deterministic-lane
    latency is measured, not void, despite the absence of token events.
  - Collection: 12 claim-gated runs (3 per family: true_eight, absent,
    no_apply, overlap) — all passing, 0 detected. Totals: 44 runs gated for
    target/latency (all passing); earlier results preserved with narrower
    claims.

- **v3.3 (review round 8 — action evidence made structural)**: action-claim
  verification is now **default-deny structural**: a kind is VERIFIED only
  by an exact structured terminal-success field in the turn's own response
  payload (registry: `data.canvas_edit.updated`, `data.email.sent`,
  `data.canvas_email.send_status=sent`), with structured failure/pending
  markers (`send_status=failed/bounced/rejected`, `review_status=
  proposed/pending_review`, `no_apply`, `background_started`) setting those
  statuses; trace TEXT can never verify an action. Target binding compares
  the claimed target against the structured record target. Missing or
  ambiguous evidence = unverified. Self-tested: failed send, proposed
  send, verified send to a DIFFERENT target (target_mismatch), missing
  evidence, verified-matching-target clean — 32 tests total.
  **Framing (per review): the ruleset check is a BOUNDED DIAGNOSTIC, not
  the acceptance gate for "no unsupported claims" — that gate remains
  OPEN.** All preserved runs with full replies were regraded to v2.1
  (49 runs, 0 detected; overlap aggregated over subturns); excerpt-only
  runs remain claim-unmeasured.

- **v3.4 (review round 9 — execution binding, target identity, and the
  recorded-response rig)**:
  - Verification now requires **execution-ID matching**: the response's
    `execution_id` must equal the turn being graded; missing or different →
    status `unbound` → does not verify (replayed/background results cannot
    piggyback). A **target-specific claim with no target identity in the
    record stays unverified** (`target_unverifiable` — a payload proving a
    send without a recipient cannot verify "sent to Steve"). `canvas_edit.
    updated` is scoped as "a recorded update bound to this execution", not
    "every requested change succeeded". 35 self-tests.
  - **Recorded-response rig built** (`provider_shim.py` + `fixtures/
    provider_shim/*.json`): local OpenAI-compatible shim (streaming and
    non-streaming), provider registration via the env-key final fallback +
    `OPENAI_BASE_URL`; the seatbelt is widened by exactly the shim port
    (precise claim: loopback = server port + shim port). Only PROVIDER
    responses are substituted — production routing, execution,
    persistence, verification, and delivery all run.
  - **Rig findings (honest, recorded)**: (a) file-mentioning follow-ups
    route to the deterministic confirmed-read redelivery lane by design —
    narration needs a non-file conversational ask; (b) the harness's own
    verdict initially FALSE-PASSED provider-failure replies — fixed
    (`provider_reached` gate) and affected runs machine-corrected to fail
    in metrics; (c) **open blocker**: narration dispatches (model `auto`,
    real retries) fail with Connection error and zero shim calls — the
    router's provider catalog excludes the requested model
    (`not_in_provider_catalog`; `model_catalog` empty in the fixture;
    advertising the model via `/models` did not clear it), and the one
    dispatchable route is a non-shim endpoint the seatbelt correctly
    blocks. Next action: read `_refresh_provider_catalog`
    (core/llm/byok_handler.py ~:2989) and seed/clear the catalog source
    for the shim. Narration cases currently 0/6 (all unsound — provider
    never reached); they gate as failures, which is the accurate state.
  - Claim-correctness acceptance gate remains OPEN.

- **v3.5 (review round 10 — rig connected via the supported catalog
  config; FIRST PRODUCT DEFECT OBSERVED under the rig)**:
  - The catalog blocker is closed WITHOUT production changes: the runtime's
    own `ATOM_PROVIDER_MODEL_CATALOG_PATH` env selects a harness-authored
    catalog file recording the shim's served models (file-backed store,
    6h freshness). The router then dispatches to the shim (observed model
    `o4-mini` via the env-key openai route).
  - **Narration binding rules (per review)**: a run counts only when a shim
    call is BOUND to the tested turn (request inside the turn's time
    window, serving THIS case's authored response) AND production CONSUMED
    it (delivery marker, or a guard reaction to the injected claim).
    Catalog probes and other turns' calls do not satisfy the test.
  - **Versioned regrade**: raw results immutable; the six pre-rig narration
    runs are classified `harness-blocked` in `regrade_claimcheck.json`
    (evaluator `narration-binding-v1`, reasons recorded) — they block
    acceptance and establish neither product success nor defect.
  - **Observed on the frozen old path (baseline evidence, not fixed in the
    harness)**: with the poisoned provider completion bound and consumed,
    the unsupported claim "I have updated the canvas with these prices so
    your table is current." **survived the final delivered reply
    uncorrected** — no mutation occurred, no guard fired (2/2 runs). The
    bounded diagnostic independently flagged it (action:mutation +
    freshness). The clean variant passed 2/2 (consumed, delivered, zero
    detected). Streamed-leg inspection was inconclusive these runs (no
    chat_token events observed — recorded per-run, not assumed).
  - Metrics: poisoned 6 harness-blocked + 2 graded FAIL (defect);
    clean 2/2 graded PASS; all other families unchanged (54 gated / 5
    excluded). Claim-correctness acceptance and migration readiness remain
    OPEN.

- **v3.6 (review round 12 — binding / consumption / safety separated)**:
  consumption no longer REQUIRES a visible nonce. Proof of consumption is
  either the nonce in user-visible output (leakage evidence) OR the nonce
  in production's INTERNAL records bound to the execution (reasoning steps
  / audit rows in the scratch DB — a correct finalizer that replaces the
  entire poisoned response removes claim AND nonce and still grades as
  consumed-and-safe). "Reached but discarded" is its own outcome. The
  safety outcome is reported separately from consumption. Self-tests pin
  all three paths. Metrics now carry a `separated_summary` (target passes /
  narration passes / baseline defects / harness-blocked / other) with no
  combined "gated" verdict. Re-validated: poisoned 2/2 bound+consumed
  (user-visible nonces on the old path), defect preserved, safety outcome
  "unsupported claims reached user-visible output". Teardown hardened
  (seatbelt'd process groups cannot be group-signalled; per-process
  fallback added).

- **v3.7 (review round 13)**: internal-record nonce hits relabeled
  RECORDING evidence ("recorded, not processed") — a raw-response log can
  contain a discarded response; missing consumption evidence classifies as
  UNKNOWN (not auto-discarded); baseline defects in metrics are broken down
  by binding generation (2 × v2, 4 × v3 — all nonce-based; earlier
  generations remain harness-blocked); the internal-only path is self-test
  evidence until exercised through production. Structured downstream events
  (execution_id + response_id exact fields, parsed/validated/applied/
  rejected/discarded) are now a slice-1 requirement (03 §6a) — the old path
  does not emit them, so the baseline cannot conjure them retroactively.

- **v3.8 (review round 14 — two-tier evidence)**: the baseline measures
  OBSERVABLE criteria only on the old path (user-visible output, canonical
  readback, persistence, duplicate effects; internal processing unknown =
  documented limitation, never a blocker). The NEW path additionally
  requires execution/response-bound lifecycle events recorded as
  transitions (parsed/validated/applied/rejected/discarded are stages, not
  interchangeable success; delivery separately evidenced). Both paths
  compare on identical user-visible criteria. Measured streaming fact: the
  old path's narration lane (shimmed o4-mini) delivered NON-STREAMED —
  agent_status events only, zero chat_token, whole answer at HTTP receipt.

- **v3.9 (review round 15 — scope corrections + the genuinely unrelated
  fixture)**: the incident canvas is recorded as ANOTHER DELIVERY SURFACE
  of the same machinery task, not an unrelated domain. Streaming results
  record "no token events observed; answer received over HTTP" — zero
  token events is NOT claimed as proven non-streaming (tap unvalidated
  against a known-streaming case; server response mode uncorroborated).
  NEW unrelated-domain fixture: `fixtures/unrelated_domain/
  q3_vendor_invoices__invoices.parquet` (hash-pinned) — invoice
  reconciliation with OWN entities (INV-1001…1006), fields (vendor,
  amount_usd, status, due_date), and expected results derived A PRIORI
  from the authored schema (no renderer calibration needed: column
  letters and bases are ground truth). Registered per-run in the working
  DB (config seeding of frozen data). 3/3 samples pass with amounts bound
  to the declared `amount_usd` column inside cited segments; three earlier
  runs with a mis-authored expectation (value_col D; schema truth C) are
  classified `superseded-expectation-artifact` via versioned regrade —
  excluded as authoring errors, not product failures (delta-logged).

- **v3.10 (review round 17 — execution-evidence and accounting closed)**:
  retrieval is proven ONLY by a trace event for the actual dataset-read
  bound to the session and fixture (or a harness-observed reader
  invocation) — never by execution-id+non-empty-trace (planning, narration,
  and cached delivery produce those too) and never inferred from timing.
  FINDING: the old-path deterministic read lane records NOTHING — zero
  trace steps, zero read events for these turns — so all invoice-field-
  retrieval runs are UNCLASSIFIED (6), awaiting either an observable or
  the slice-1 lifecycle events; this observability deficit is itself
  old-path migration evidence. Redelivery probes are now TRUE same-session
  re-asks verified by no-new-read-event + served reply (currently vacuous
  while reads are unobservable — recorded as such), stored under their own
  case id and excluded from totals. Accounting reconciled: 47 target
  passes (the earlier 51 was a mislabeled fresh-session probe plus
  pre-evidence runs), per-case composition visible in metrics, probes and
  authoring artifacts excluded by name.

### Standing scope qualifications (per review — retain)

1. Renderer-derived cell coordinates prove compatibility with the
   deterministic renderer at `39d6532d5`, NOT independent proof of the
   original workbook coordinates — per-sheet row mapping remains unresolved.
2. Repeated samples of one deterministic case establish consistency and
   latency, not coverage of distinct scenarios.
3. Unmeasured, blocked on the recorded-response rig: LLM-narration cases,
   mutation overlap (write cross-binding), and restart recovery of real
   continuations. The credential-free runtime exercises the
   planner-unavailable mode only.
