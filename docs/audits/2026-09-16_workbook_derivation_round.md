# Workbook Derivation Round — routing identity, evidence lanes, acceptance

**Date:** 2026-09-16 · **Tested revision:** `8d9a2d97ae47` (clean tree, `dirty: false`)

This round answers the external review that followed the gap-closure matrix. It
separates **implemented** / **isolated verification** / **live verification**
and states plainly what is still blocked.

---

## Tested revision and effective configuration

| Thing | Value |
|---|---|
| HEAD | `8d9a2d97ae47` (`source_id` from `GET /api/health`: `8d9a2d97ae47`, `dirty: false`) |
| Live instance at final acceptance | pid **65439**, started 2026-09-16T16:03:58Z — and a restart by the concurrent session mid-run (the acceptance script flagged "served by 2 different backend instances") |
| Turn budget | `CHAT_TURN_BUDGET_DEFAULT_SECONDS = 95.0` (`ATOM_CHAT_TURN_BUDGET_SECONDS` overrides) |
| Provider catalogues (discovered, persisted) | `deepseek` 2 identifiers · `opencode-go` 71 · `openrouter` 444 |

---

## 1. Provider/model identity through fallback — IMPLEMENTED, VERIFIED

**What was wrong (three separate mechanisms):**

1. `get_fallback_models` returned bare model names, discarding the provider.
2. `stream_completion`'s model-level recursion passed the ORIGINAL `provider_id`
   with the next model, so a model ranked for provider B was dispatched to
   provider A.
3. `_provider_serves_model` returned `True` for every gateway provider
   ("the gateway client is authoritative for any model routed to it"), which
   made every catalog identifier eligible for every gateway.

**Fix:** a route is `(provider, model)` and travels together through dispatch,
fallback and retries (`get_fallback_routes`, `fallback_routes=`,
`_route_for_model` for legacy name-only callers).

**Isolated:** `tests/test_model_route_identity.py` — **42 tests**, including
"first route fails and a different provider completes", "the fallback is not
dispatched to the original provider", "no duplicate output", "no route
dispatched twice", task requirements travel with the fallback, and cancellation
after visible output stops the ladder.

**Live:** the forced-unsupported-primary probe answered `Red` from
`openrouter / z-ai/glm-5.3-flash` with the dispatch chain visible in the log.

## 2. Catalog knowledge vs executable routes — IMPLEMENTED, VERIFIED

`core/llm/model_route_registry.py`: a persisted, thread-safe catalogue of which
identifiers each provider was observed to serve, with freshness
(`fresh` / `stale` / `unknown`), a discovery-failure record that KEEPS the last
verified set, and an auth probe recorded separately from discovery. Every
candidate gets a decision (`verified_served`, `previously_verified_stale`,
`not_in_provider_catalog`, `provider_catalog_unknown`, `provider_not_configured`,
`local_runtime_served`, `explicitly_requested_route`).

**Measured on the live ladder:** `ranked routes reconciled: 17 dispatchable,
108 excluded` — the incident's ladder paired gateway identifiers with the
first-party `deepseek` provider (2 served identifiers); 9 of the top 12 were
unservable.

**Identifier matching is EXACT.** An earlier version stripped vendor namespaces,
so `deepseek/tencent/deepseek-v4-pro` "matched" `deepseek` and the endpoint
answered `400: the supported API model names are deepseek-flash,
deepseek-v4-pro, but you passed tencent/deepseek-v4-pro`. The same underlying
model under two providers is now two routes, each with its own identifier.

**Availability guard, stated:** if NOTHING is verified the unreconciled ranking
is used with a warning (an empty ladder is a self-inflicted outage) — discovery
failure never means "everything is supported".

## 3. Authentication vs model rejection — IMPLEMENTED, VERIFIED

`classify_failure()` returns one of `invalid_credential`, `unsupported_model`,
`entitlement`, `quota_exhausted`, `rate_limited`, `malformed_request`,
`transport`, `empty_output`, `unknown`, with credential-shaped material
redacted from the recorded detail.

**Model rejection is checked BEFORE credential rejection** — some gateways
answer an unsupported model with `401` and a body naming the model, and reading
that as a credential failure disables a working provider.

**Response by cause:** provider-scoped causes (credential/entitlement/quota)
pause the PROVIDER process-wide with a TTL, so a 401 is not retried across every
model; route-scoped causes bench only that `(provider, model)`. Recovery is
explicit: storing or deleting a key calls `invalidate_provider_failures()`,
which clears the pause and the catalogue so the next turn re-discovers.

**Live:** after a 401 the log shows `Skipping provider opencode-go for this
attempt: invalid_credential` and the ladder continues on another provider.

**Measured nuance, reported not hidden:** a direct probe of
`opencode-go/gpt-5.3-codex-spark` returns `401 AuthError "Invalid API key."`
while the same provider's `models.list()` answers — so the Settings "Test"
probe establishes reachability, not authentication. (An earlier chip in this
round claimed that provider "never works"; that was wrong — a streaming reply
was later observed completing on it, so the failure is conditional, not
absolute.)

## 4. Bounded fallback sequence — IMPLEMENTED, VERIFIED

Isolated regression: `tests/test_model_route_identity.py` (dispatch pairs,
retained task requirements, cancellation, no duplicate output, no route twice).
Live: a forced unsupported primary reached a valid route on another provider and
answered.

**Zero-latency failure rows — checked as requested.** The live table carries
160 `success=false` rows with `latency_ms = 0`; 129 of them belong to ONE turn
(`65ac1668-…`, 13:42:04–13:42:19) with one row per candidate model, identical
task-default features and no cost — a candidate enumeration, not 129 executed
generations. The router report detects that shape (`suspected_candidate_sweeps`)
and excludes it. New regression: a route that is SKIPPED (provider cooling down,
identifier not served) writes **no** outcome row — verified by two tests that
assert no `_record_outcome_feedback` call happens for a route that was never
dispatched. The writer of the historical 129-row sweep could not be attributed
from the table alone.

## 5. Acceptance criteria strengthened — IMPLEMENTED, VERIFIED

`backend/scripts/acceptance_replay_canvas.py` rewritten (by a delegated agent,
reviewed here): keyword-presence scoring replaced by explicit per-case criteria
over three evidence kinds — response metadata/route/serving-instance, the
persisted turn trace for stage evidence, and read-only in-process store checks
(LanceDB communications, attachment ledger, sheet-dataset Parquet + formula
sidecar). `tests/test_acceptance_criteria.py` — **30 tests**, one per criterion
proving a keyword-only reply FAILS and a substantively correct one PASSES.

Delivery and quality are separate verdicts; a provider failure is **failed
end-to-end delivery with quality not evaluated**; the failing stage is recorded;
each case carries its own `X-Atom-Serving-Instance`.

**Ground truth the corpus established (read-only), which changes what "correct"
means for two cases:**
* quote — the `$ 5,350.00 – 10 % in stock` line IS in the ingested mail from
  `joelseguin@seguinmach.com`, "FW: RFQ - Foot shear", 2026-08-26 14:06:28.
* directional — **exactly one** store message carries `PRICE VIPUL (6).xlsx`:
  `chandrakant@brennan.ca → rish@brennan.ca`, internal (both `@brennan.ca`).
  There is no outbound-to-counterparty carrier, so the correct answer is "no sent
  message carries it", which is what the reply says.
* derivation — `PRICE VIPUL (6).xlsx` / Sheet1 / row 235: `D235=P235`,
  `G235=F235*0.9`, `I235=H235+700`, `K235=J235*1.02`, `L235=K235/0.87`,
  `M235=L235/0.86`, `N235=ROUNDUP(M235,0)`; **`U235`/`O235` are empty for that
  row**, so any answer using an exchange factor for row 235 is fabricating.
* **Product defect found by the corpus (filed, not fixed):** the comms store's
  `direction` column is unusable — 7 329 of 7 339 rows say `inbound`, including
  messages the mailbox sent. The acceptance script derives direction from
  sender/recipient domains instead of trusting it.

## 6. Runtime attribution — IMPLEMENTED, VERIFIED

`core/runtime_identity.py` captures, ONCE at process start: `revision`,
`dirty` + `dirty_digest` over modified/untracked file CONTENT, `source_id`
(`<revision>[-dirty.<digest>]`) and `instance_id`. `GET /api/health` reports it;
`/api/chat/message` stamps `X-Atom-Serving-Instance` / `X-Atom-Source` on every
response (including error paths), so a caller attributes ITS OWN request.

**Demonstrated working:** the pre-run health read showed
`8d9a2d97ae47, dirty: false` after the concurrent session committed, while an
earlier run showed `6354fdf183bd-dirty.<digest>` — the field distinguishes a
committed tree from a dirty one, and the acceptance script discards a run whose
cases report more than one `source_id`.

## 7. Grounding feedback through an evidence-bearing turn — VERIFIED LIVE

The accounting now reads a REAL rate instead of 1.0-by-construction:

    generations=4  fabricated=2  grounded_ok=2  unevaluated=445
    unknown=264    duplicate_rows=34  malformed_rows=0   rate=0.5

`grounding_ok` is emitted only when the figure-grounding check RAN and found
nothing (`_grounding_ran` guard), through the orchestrator's own guard, and it
survives restart (read back from the DB after a restart). **Probes do not
manufacture it:** three provider-auth probes and the reliability harness's
authenticated calls added **0** rows and **0** verdicts (`--allow-learning-writes`
is off by default; its guard suppressed 7 real learning writes during a bounded
run).

## 8. Coherent acceptance — the derivation now works; the RUN does not close

### The derivation succeeds through the real canvas (verified twice)

    "I opened PRICE VIPUL (6).xlsx — Sheet1, row R235 (ingested 2026-09-11).
     The workbook's formulas show the listed price 7519 was computed step-by-step
     as follows (cell refs from that sheet): F235 (Factory Price) = 5350.0;
     G235 = F235 * 0.9 → 4815.0; I235 = H235 + 700 → 5515.0 (Freight);
     K235 = J235 * 1.02 → 5625.3 …"

A second run additionally named the unresolved intermediate: *"following the
sheet's chain, N235 rounds to 7521, but the LIST Price recorded is 7519 … the
extract does not show O235 … so I cannot confirm the exact multiplication"* —
i.e. the gap is left explicitly unresolved rather than invented.

**Three stacked defects had to be fixed, each hidden behind the last:**

| # | Defect | Evidence | Fix |
|---|---|---|---|
| 1 | The workbook probe never fired | `_distinctive_figure_phrases("…the 7519 listed price…")` → `[]`; a bare integer is not a "figure phrase" to a currency recogniser, so `figures` was empty and the lane returned `None` | a 3–6 digit integer within 40 chars of a value word is probed, scoped to derivation asks |
| 2 | The lane was planner-dependent | only called inside the plan branches; a planner timeout skipped it entirely | it now runs as a guarantee for any derivation ask and logs its stage |
| 3 | My idempotence guard suppressed it | the guard tested `"DATASET CATALOG" in _tool_block`, which the PLANNER's own `datasets.search` block also satisfies (4 188–52 361 chars of other sheets' rows) | the guard now requires the lane's own signature (`FORMULAS FOR THE MATCHED ROW`) |

### What still blocks a clean 5/5: LATENCY, not routing

| Case | Delivery | Quality | Latency |
|---|---|---|---|
| quote | answered | **pass** | 71.9 s |
| directional | answered | **pass** | 276.3 s |
| derivation | **structured_error** (`turn_budget_exceeded`) | not evaluated | 121.0 s |
| control_unrelated_source | transport_error (restart mid-run) | not evaluated | 366.0 s |
| control_missing_evidence | **structured_error** | not evaluated | 151.1 s |

A FINAL confirmation run on the committed revision (`8d9a2d97ae47`, clean tree,
pid 65439) is blunter still: the derivation ask returned
`turn_budget_exceeded` after **201 s** with no reply at all. The variance
(148 s → 201 s, and 96.6 s earlier) is itself part of the finding: the turn's
cost is dominated by a stage whose duration depends on how long a reasoning
model spends producing nothing visible before the fallback fires.

Intended budget **95 s**; measured turns 112–366 s. Mechanism, from the stage
log of a 148 s derivation turn:

    [derivation] workbook lane: 1286 chars of dataset evidence (leading)  <- overlapped, ~free
    [stage-timing] tool plan (overlapped=True): 7.5s
    [stage-timing] tool exec: 12.4s
    WARNING: chat streaming produced no tokens — falling back
    [stage-timing] reply generation: 38.8s

The turn pays for a **zero-visible stream AND then a full non-streaming
regeneration** (heavy evidence + a reasoning model that spends its budget
invisibly — a pattern the code already documents). Each stage respects its own
cap; the TURN total does not, because the budget is checked per wait rather than
against the turn.

**Done this round to shorten it:** the deterministic derivation lane (1–20 s,
plan-independent) is now STARTED before the planner and awaited at the append
point, so its cost overlaps the planner instead of queueing behind it.

**Not done:** the zero-visible-stream-plus-regeneration cost (~40 s per
occurrence) is unaddressed. Also unaddressed: the acceptance run itself was
confounded a third time by a concurrent restart, so its 2/5 is **not a
verdict** — the script says so itself.

---

## Retained limitations

| Item | Why it stays open |
|---|---|
| Turn latency vs the 95 s budget | Mechanism measured (failed stream + full regeneration); the budget is enforced per wait, not per turn |
| Derivation case re-run | Needs a window with no concurrent restarts; the script discards runs with >1 serving instance |
| Comms `direction` column | 7 329/7 339 rows say `inbound` including sent mail; acceptance derives direction from domains instead. Not fixed |
| 129-row candidate sweep | Detected and excluded; writer not attributable from the table |
| `opencode-go` completion 401 | Conditional (a stream completed on it later); the Settings "Test" probe cannot distinguish reachability from authentication |
| `scripts/check_undefined_names.py` | New guard: two defects this round were `compile()`-clean and only failed at runtime behind an `except` (a stale `_fb_models` that made every affected turn return the canned template, and `collect_team_signers` called but never imported) |
| Office-file authorization, legacy `.doc`/`.ppt` extraction, router comparisons | Separately owned; not touched here |

## Claims deliberately not made

- The acceptance suite has **not** passed 5/5 on a single verified instance.
  Saying otherwise would repeat the error this round is correcting.
- "The routing failure is fixed" is supported for the ROUTE layer (reconciliation
  + identity + cause-aware response, verified live); it is **not** a claim that
  the end-to-end acceptance closes, which is blocked on latency.
- No claim that latency is irrelevant: it is measured, attributed to a named
  mechanism, and reported against the 95 s budget.

---

# Addendum — goal round 1 (2026-09-16 12:25–13:20 EDT)

Three more root causes were found and fixed after the round above was written.

## A. Route reconciliation was only wired into the FALLBACK list

`_reconcile_ranked_routes` ran inside `get_fallback_routes`, so every OTHER
consumer of `get_ranked_providers` — the structured path, `generate_response`,
`LLMService`, the gateway, the MCP tools — still received the UNRECONCILED
ranking. That is why the log carried
`Structured generation … deepseek/deepseek-v3-2-251201`, a model the `deepseek`
provider does not serve (its catalogue is 2 identifiers), and why those calls
burned the turn budget before the reply.

**Fix:** reconciliation now runs INSIDE `get_ranked_providers`, so every
consumer gets dispatchable routes. Measured: `118 → 15 dispatchable,
103 excluded`, each with its reason.

**Effect on the derivation:** the isolated derivation turn went from
**201–270 s with no answer (`turn_budget_exceeded`)** to **102 s with the full
verified chain**, and the structured calls no longer name unservable models.

## B. The directional case: two defects, one behind the other

1. **The join was never called for a mail-shaped ask.**
   `_messages_carrying_file` (attachment → carrying message) is only invoked as
   an appendage to a **dataset** hit — it iterates the files a dataset search
   already found. "Which emails did we send that carried X as an attachment?"
   makes the planner run `outlook.search`; the dataset lane never fires, so the
   carrier line never reaches the evidence.
   **Fix:** a deterministic, planner-independent carrier leg for asks that are
   about a carried file (`_mentions_attachment`, narrow regex).

2. **Inside the join, matches were taken in dict order.**
   The query's tokens are `{price, vipul, list}`; two unrelated vendor price
   lists share `{price, list}` and came first, so the real carrier — the only
   name sharing `vipul` — was cut by `limit`.
   **Fix:** weight each shared token by `1/df` (a token in one attachment name
   discriminates; one in fifty does not) and rank on that.

**Verified end to end, twice, on live instances:**

```
"which emails did we send that carried the PRICE VIPUL price list as an
 attachment?"  ->  46 s and 48.9 s, answered
"I found one email in the mailbox carrying that file:
 From: chandrakant@brennan.ca  To: rish@brennan.ca
 Subject: Fw: RFQ - Foot shear
 Attachment: PRICE VIPUL (6).xlsx  Received: September 11, 2026, 8:07 PM"
```

That matches the independently verified ground truth for the case (exactly one
carrier; internal, brennan→brennan).

## C. A bounded instrument for the zero-visible stream

`_STREAM_FIRST_VISIBLE_SECONDS` (default 30, `ATOM_STREAM_FIRST_VISIBLE_SECONDS`)
abandons a streaming attempt that has produced no visible content and spends the
remaining budget on the non-streaming fallback. Previously a reasoning model
emitting only hidden thinking held the stream until the WHOLE budget was gone,
and the 40 s fallback reserve only binds when more than 55 s remain — so the
fallback got nothing and the user received `turn_budget_exceeded`.

## Verified this round

| Check | Result |
|---|---|
| `tests/test_attachment_carrier_ranking.py` (new) | 12 passed — decisive-token ranking, detector, negatives |
| `tests/test_derivation_lane_independence.py` | 9 passed |
| `tests/test_model_route_identity.py` | 42 passed |
| `tests/test_acceptance_criteria.py` | 39 passed |
| `tests/unit/test_byok_handler*.py` | 4F/222P = pristine baseline (no regression from the central reconciliation) |
| Directional acceptance case | **PASS**, verified twice end to end |
| Derivation through the canvas | verified with the full chain (workbook → sheet → row 235 → formulas → unresolved `O235`) at 102 s and 186 s |

## Still open

| Item | Evidence |
|---|---|
| One clean 5-case acceptance run on a single instance | The suite was invalidated by a concurrent restart FIVE times this round; the script's own guard refuses such runs ("served by 2 different backend instances") |
| Derivation latency vs the 95 s budget | 102–265 s measured; the host is shared with another application (load average 12–19) and the backend is restarted every few minutes by a concurrent session |
| `quote` case | PASS on one run (117.9 s), FAIL on another (155.1 s) — retrieval-flaky under load; not yet root-caused |
| Derivation reproducibility | Correct on several isolated runs, absent on two attempts that overlapped a restart mid-turn |

The completion criterion — derivation through the canvas **within the request
budget**, all cases satisfying the strengthened criteria, one verified build —
is **not met**. The routing layer, the evidence lanes and the acceptance
instrument are in place; what remains is latency and a stable measurement
window.

---

# Addendum — goal round 2 (2026-09-16 13:22–14:20 EDT)

## Measured on one verified instance (strengthened criteria)

Instance `0baf7c508fa1-dirty.eb26b684971f.90689` (port 8002, dedicated, same
code + `data/atom.db` + BYOK store):

| case | verdict | latency |
|---|---|---|
| quote | **PASS** — 5 stored messages identified, attribution corroborated, quoted terms verified in the source | 175.0 s |
| directional | **PASS** — 1 store carrier, direction verified, no phantom outbound | 92.3 s |
| control_unrelated_source | **PASS** — 12 planner/tool steps, explicit not-found, no false source claim | 128.1 s |

Instance `82a4d548d1dc-dirty.48ac68686f03.95790`:

| case | verdict | latency |
|---|---|---|
| control_missing_evidence | **PASS** — no price attributed to F-9999, explicit unresolved statement | 128.9 s |
| derivation | **FAIL** — workbook named ✓, no fabricated chain ✓, unresolved reported ✓, but **row number missing** and **0/6 chain steps stated** (a refusal) | 197.1 s |

So four of the five cases pass the strengthened criteria on the current build;
the derivation is the one that fails, and it fails **intermittently**:

* subagent's run: **PASS 6/6**, 19 asserted equalities, 159.5 s
* this session: **PASS** with the full chain at 102 s
* this session: **FAIL** (refusal) at 197.1 s and again at 264 s

## The evidence IS in the prompt when it refuses

Checked directly rather than assumed:

* the lane fires — `[derivation] workbook lane: 1286 chars of dataset evidence`
  and `[derivation] ask=True matched-row-evidence=True tool_block=22804 chars`;
* the 18 000-char budget trim does **not** drop it — against a realistic
  18 377-char block the trim keeps `R235`, `FORMULAS FOR THE MATCHED ROW` and
  `LIST Price=7519`, and says so ("3 decisive line(s) and 4 other line(s)
  omitted").

So the remaining derivation defect is **how the evidence is framed or which
model answers**, not retrieval and not the budget. That is the next thing to
take.

## Latency: the pre-reply legs, not the reply

`[stage-timing] canvas-edit plan: 69.1s` … `reply STREAMED: 10.5s to full text
(497 chunks)` … `reply generation: 20.5s`. `plan_canvas_edit` itself returns in
**0.0 s** when called directly with nothing to plan, so the cost is the
canvas-edit LEG's preparation (canvas refresh/heal, cross-canvas learnings,
identity, playbooks, fresh-data join) plus the planner legs — 60–90 s of a
turn whose answer takes 10 s. Bounding or bypassing that leg when the
deterministic derivation lane already holds the matched row is the fix.

## Instrumentation added

`Attempting stream with provider: %s (requested: %s) model=%s` and a warning
when a stream ends with zero visible chunks, naming the `finish_reason` — the
recurring "produced no tokens" warning was previously unattributable.

## Correction

Two `NOT_EVALUATED` cases in the 18:01 run were caused by **me** restarting the
dedicated instance for instrumentation mid-run, not by the product. Recorded
here because the run's own guard could not tell the difference.
