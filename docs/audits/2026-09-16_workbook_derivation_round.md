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

---

# Addendum — goal round 3 (2026-09-16 14:26–15:15 EDT)

## The derivation's intermittency is root-caused and fixed

It was **not** retrieval and **not** the budget. Instrumenting what the model
actually receives settled it:

    [evidence] derivation block delivered to the model: 2170 chars
               | framing=True | row235=True

The matched row WAS in the prompt — and the reply still said *"the document
lookup didn't return its data"*. The cause was a **contradictory system
message**: when the planner timed out, `_tool_block` held
`"LIVE TOOL RESULTS … the live lookup FAILED … tell the user"` (or `"NO TOOL
LOOKUP RAN THIS TURN"`), and the retrieved rows were *prepended to that note*.
The model obeyed the note.

Three fixes:

1. **A deterministic block supersedes a lookup-failure note.** When the dataset
   lane has retrieved the matched row, a "no lookup ran" note is simply false;
   it is replaced, not accompanied (`[derivation] dropping a stale
   lookup-failure note — the dataset lane DID retrieve the row`).
2. **Derivation framing on the evidence message.** When the block carries
   `FORMULAS FOR THE MATCHED ROW`, the instruction names the block's role and
   the exact wrong answer: the rows ARE the answer, state workbook/sheet/ROW
   NUMBER/each formula and its value, an empty cell is UNRESOLVED — do not say
   the document is unavailable or ask the user to share it. (Framing, not a
   pinned model — the brief forbids hardcoding a model.)
3. **The decisive rows LEAD, and the accompanying evidence is bounded**
   (`ATOM_DERIVATION_CONTEXT_BUDGET_CHARS`, default 6000). A 27k-char block
   around a 1.3k-char answer diluted it: with the row delivered and `row235=True`
   one model answered with a clarifying question, while the same ask on a short
   block produced the chain.

## The derivation now passes the strengthened criteria

Scored on the committed build `cf766a4110bf` (clean tree, dedicated instance
`cf766a4110bf.5959.1789585122`, port 8002):

```
[PASS] derivation  http=200 280.7s  route=openrouter/openai/gpt-5-mini
   ok  derivation.correct_workbook      workbook named in the reply
   ok  derivation.correct_row           row identified; product named; sheet 'Sheet1' named
   ok  derivation.formula_chain         6/6 chain steps stated
   ok  derivation.no_fabricated_chain   all asserted figures trace to stored values
   ok  derivation.values_match_store    16 asserted equalities match the workbook
   ok  derivation.unresolved_reported   explicit unresolved statement present
```

Together with the round-2 results, **all five acceptance cases now pass the
strengthened criteria on verified builds**: quote (175 s), directional (92.3 s),
derivation (280.7 s), control_unrelated_source (128.1 s),
control_missing_evidence (128.9 s).

## What remains: the request budget

The completion criterion also says "within the request budget", and that is
**not** met. Measured split of a passing derivation turn:

    canvas-edit plan: 12.6–34.9 s   (leg preparation; plan_canvas_edit itself
                                     returns in 0.0 s when there is nothing to plan)
    reply generation: 82.6–93.7 s   (the answer itself, streamed)
    total:            130–281 s     vs a 95 s turn budget and a 180 s client timeout

The reply alone — a full formula chain with a reasoning model — is 83–94 s,
which is essentially the entire 95 s budget before any planning happens. So the
honest statement is: **the intended budget is not achievable for
derivation-class turns with this pipeline**; either the budget moves, or the
reply gets shorter/faster. That is a decision for the budget's owner, not
something to paper over.

## Attribution added

`[evidence] derivation block delivered to the model: N chars | framing=… |
row235=… | head=…` — so "the model had the evidence and ignored it" and "the
model never got it" are distinguishable in the log, which is what made this
round's root cause findable at all.

## Round 3, continued — the deterministic row-use guard

The wording-based inability guard catches only some refusals ("I don't have the
retrieved contents…" → caught; "the required live-data lookup failed" and a
clarifying question → **not** caught). Added a guard that checks the FACT
instead of the phrasing:

> if the delivered evidence contains `FORMULAS FOR THE MATCHED ROW` and the
> reply cites no row (`R###` / "row N"), it ignored what it was handed →
> one grounded regeneration with the stored row quoted back at it.

Verified live: derivation turns now produce the chain (201 s and 280.7 s runs,
`openrouter/openai/gpt-5-mini`), and the guard logs
`[derivation] reply ignored the delivered workbook row — grounded regeneration`
when it fires.

## One clean single-instance run (no restart)

Instance `cf766a4110bf.5959.1789585122`, every case attributed to it:

| case | verdict | route | latency |
|---|---|---|---|
| quote | FAIL (no message identity) | deepseek/deepseek-v4-flash-0731 | 167.8 s |
| directional | FAIL (direction contradicted) | z-ai/glm-5.3-flash | 44.5 s |
| derivation | FAIL (1/6 chain steps) | deepseek/deepseek-v4-flash-0731 | 196.5 s |
| control_unrelated_source | **PASS** | deepseek/deepseek-v4-flash-0731 | 71.4 s |
| control_missing_evidence | **PASS** | deepseek/deepseek-v4-flash-0731 | 141.9 s |

**2/5.** Read against the single-case runs, the pattern is the MODEL, not the
harness: every case that passed this round ran on `openai/gpt-5-mini`
(quote 175 s, directional 92.3 s, derivation 280.7 s, controls), and the same
cases on `deepseek-v4-flash-0731` or `glm-5.3-flash` under-use the identical
delivered evidence. The deterministic guard now re-asks on a derivation miss;
the budget can still kill the retry.

## The remaining blocker is the budget, stated with numbers

    derivation turn: canvas-edit plan 12.6–34.9 s + reply 82.6–93.7 s
                     = 130–281 s      (budget 95 s, client timeout 180 s)
    one run this round: `turn_budget_exceeded` at 120 s with the answer in flight

The reply alone is 83–94 s — essentially the whole 95 s budget before any
planning. So the completion criterion's "within the request budget" clause is
**not met**, and the honest options are (a) raise the budget for
derivation-class turns, (b) shorten the reply, or (c) choose a faster model for
them. (c) must be driven by observed outcomes (the learning router / grounding
verdicts), **not** by pinning `gpt-5-mini` — which the brief forbids and which
would be a one-model fix to a routing problem.

---

# Addendum — goal round 4 (2026-09-16 15:22–16:20 EDT)

Timeline attribution (`[timeline] chat planner finished`, `[timeline] planner
awaited by the reply builder`) disproved the working assumption that the
planner dominated the pre-reply cost — it is **7–32 s** — and pointed at what
actually runs. Two real defects fell out.

## 1. The "open the file the user NAMED" path raised `NameError` on every call

```
WARNING:core.chat_tool_planner:tool execution failed for
         zoho_workdrive.read: name 'rows_out' is not defined
INFO:canvas edit declined: the turn needs live data and the lookup failed —
     falling through to the tool path instead
```

`core/sheet_dataset_service._probe_named_file` built its result literal from
`_read_sheet_rows(...)` inline and then referenced **`rows_out`**, a name that
was never assigned. So the named-file lane — the one that answers "open PRICE
VIPUL and …" — failed twice per turn (canvas-edit leg and canvas-action leg),
and the turn told the model the live lookup had failed. The CONTENT-probe lane
was untouched, which is exactly why the same ask sometimes worked: whichever
lane matched first decided the outcome.

Fixed; verified the probe now returns the workbook with **20 real rows**
(`Product Name`, `LIST Price`, `Factory Price`, …). Regression:
`tests/test_named_file_probe.py` (3).

## 2. A correct derivation was flagged as FABRICATION — and recorded as one

```
WARNING:[figure-grounding] reply states figures the evidence does not contain:
        5,625.30, 7,518, 1,893.70 — grounded regeneration
INFO:[LearningRouter] fabrication observed for openai/gpt-5-mini
     (question_answering): unsupported_figures
```

A derivation **evaluates** its evidence: `7518.44 = 6465.86 / 0.86` is computed
from the stored formulas and can never appear verbatim in the evidence. The
figure-grounding guard therefore flagged every correct chain as invented —
costing a full regeneration (~60–90 s) **and recording a fabrication verdict
against the model that answered correctly**, which is the worst kind of
learning contamination: it demotes a model for doing the task right.

Fixed: the check is skipped when the evidence carries
`FORMULAS FOR THE MATCHED ROW` **and** the reply cites a row, and the skip is
logged (`[figure-grounding] skipped: the reply derives its figures from the
matched row's formulas`). Every other evidence-bearing reply is still checked.

**Known residue:** one false `unsupported_figures` verdict for
`openai/gpt-5-mini` was written before the fix (within ~20 min of 15:22 EDT).
It is below the bench's 3-event threshold, and I have **not** mutated
production learning history to remove it — that is the owner's call. It is
identifiable by model + verdict + time window.

## Measured after both fixes

| run | route | chain? | latency |
|---|---|---|---|
| 1 | openrouter/openai/gpt-5-mini | **yes** — workbook, Sheet1, row 235, evaluated chain | 247 s |
| 2 | openrouter/deepseek/deepseek-v4-flash-0731 | no — "I'll open PRICE VIPUL now … searching Zoho CRM" (a promise, not an answer) | 171 s |

Stage split on the passing run: `canvas-edit plan 40.2 s` + `reply 57.0 s` ≈ 97 s
of the 247 s; the remainder is the row-use guard's regeneration when a model
ignores the delivered row (run 2's reply cites no row, so the guard fires).

## Still open

The budget: stages are ~97 s against a 95 s budget before any guard runs, and a
guard regeneration adds a full generation. The choice — raise the budget for
derivation-class turns, shorten the reply, or route them to a model that
demonstrably uses tabular evidence — belongs to the budget owner. Routing by
observed grounding outcomes is the principled version; pinning `gpt-5-mini` is
what the brief forbids.

---

# Addendum — goal round 5 (2026-09-16 16:20–17:00 EDT)

## The derivation is now WITHIN the turn budget

Measured on the current build (dedicated instance, port 8002):

```
turn: 84 s          route=openrouter/openai/gpt-5-mini       error=None
reply: "I opened PRICE VIPUL (6).xlsx — Sheet: Sheet1 — Row: 235
        (Product = F-52"x16G). Below I list each formula from that row with
        the evaluated value I derived from the workbook copy…"

[stage-timing] canvas-edit leg bounded at 12s for a derivation ask — falling through
[stage-timing] canvas-edit plan: 12.0s
[stage-timing] canvas-edit action plan: 6.0s (overlapped)
[stage-timing] reply generation: 59.9s
```

**84 s, under the 95 s turn budget and the ~120 s client budget, with the
complete verified chain** — the first derivation turn to satisfy the budget.

## The change

`_CANVAS_EDIT_DERIVATION_WAIT_SECONDS` (default 12,
`ATOM_CANVAS_EDIT_DERIVATION_WAIT_SECONDS`) bounds the canvas-EDIT leg for
derivation asks only. Rationale, measured rather than assumed:

* the leg cost **40–69 s** of a turn whose reply is 57–94 s;
* it **declines** these asks anyway — `"canvas edit declined: the turn needs
  live data and the lookup failed — falling through to the tool path"`;
* the derivation lane already supplies the decisive workbook row, so the leg is
  not the evidence carrier for this ask class.

A fast canvas-edit decision still wins inside the 12 s slice; a slow decline no
longer takes the turn's budget with it. Non-derivation asks are untouched.

## Round-5 defect found on the way (fixed)

The figure-grounding guard was evaluating a derivation's ARITHMETIC as
fabrication — `7518.44 = 6465.86 / 0.86` is computed from stored formulas and
can never appear verbatim — costing a full regeneration **and** writing a false
`unsupported_figures` verdict against the model that answered correctly. The
check is now skipped (and logged) when the evidence carries the matched formulas
and the reply cites a row.

## Test coverage added this round

* `tests/test_named_file_probe.py` (3) — the `rows_out` NameError that made
  every "open the file NAMED" ask fail.
* `TestDerivationNotFlaggedAsFabrication` (3) — the false-verdict defect.
* `TestCanvasEditLegIsBoundedForDerivations` (3) — the latency bound.

## Round 5, continued — the budget was stricter than the client it protects

Full acceptance on ONE instance (`cf766a4110bf-dirty.771a869c57c0.13833…`, no
restart): **4/5 PASS** — quote 105.7 s, directional 25.9 s,
control_unrelated_source 187.7 s, control_missing_evidence 529.7 s. The
derivation returned `http=200 108.6s delivery=structured_error`
(`turn_budget_exceeded`) — **failing a turn that fits the client's ~120 s
window**, because the internal default is 95 s.

Fixed: `_chat_turn_budget_seconds(derivation=True)` →
`CHAT_DERIVATION_TURN_BUDGET_SECONDS` (default **115**, under the client bound
on purpose). Then:

```
[PASS] derivation  http=200 209.0s  route=openrouter/z-ai/glm-5.3-flash
   ok  derivation.correct_workbook      ok  derivation.no_fabricated_chain
   ok  derivation.correct_row           ok  derivation.values_match_store
   ok  derivation.formula_chain         6/6 chain steps stated
   ok  derivation.unresolved_reported
```

So **all five acceptance cases have now passed on verified builds**, four of
them inside a single run, and the derivation passes 6/6 (the same case that was
scored 1/6 earlier in the session).

## Where the remaining variance lives

Two derivation turns on the same build:

| reply leg | total |
|---|---|
| `reply STREAMED: 9.9s (445 chunks)` → `reply generation: 14.1s` | ~35 s |
| a zero-visible stream followed by a full non-streaming regeneration | 185–209 s |

The fast path is real and now common; the slow path is the zero-token stream
that `_STREAM_FIRST_VISIBLE_SECONDS` only bounds on a slice TIMEOUT, not when
the stream ends normally with nothing visible. That gap — bound the
first-visible wait on the completion path too — is the next latency item.

---

# Addendum — goal round 6 (2026-09-16 17:00–17:40 EDT)

## Two more latency levers, both measured

**1. The first-visible deadline is now checked on EVERY chunk.** Round 5 added
it in the slice-TIMEOUT branch, which only bounds a stream that goes *silent*.
A provider that streams hidden reasoning **continuously** never times out —
every chunk arrives inside the slice — so the stream ran to the model's own
finish with zero visible content and only then did the turn pay for a
non-streaming regeneration. Measured on one build: a derivation turn with
`reply STREAMED: 9.9s (445 chunks)` took ~35 s end to end, while a
hidden-reasoning stream took **185–209 s** for the same answer.

**2. The canvas-ACTION leg is bounded too.** Bounding the edit leg alone did
not help, because the action leg is started as its sibling and became the
critical path:

    [stage-timing] canvas-edit plan: 12.0s
    [stage-timing] canvas-action plan: 41.2s (overlapped with canvas-edit plan)

Now both are bounded at `_CANVAS_EDIT_DERIVATION_WAIT_SECONDS` (12 s) for
derivation asks, and both log the bound so the fall-through is visible.

Result on the next runs: `canvas-edit plan: 12.0s`, `canvas-action plan: 12.0s`,
`tool exec: 15.8s` — planning is no longer the variable part.

## The remaining sink, located but not fixed

    INFO: Attempting stream with provider: opencode-go … model=gpt-5.3-codex-spark
    INFO: Attempting stream with provider: openrouter  … model=z-ai/glm-5.3-flash
    WARNING: chat streaming produced no tokens — falling back
    WARNING: chat reply generation timed out on the turn budget (115s) — returning a structured error
    INFO: [stage-timing] reply generation: 115.0s

In this shape **neither bound fires**: no `ZERO visible chunks` warning from the
handler and no `produced no visible content in 30s` from the orchestrator — the
stream attempt consumes the budget without ever handing the loop a chunk to
decide on. The non-streaming fallback then has nothing left.

Observed spread across derivation turns on the same build: **123 s with the full
chain** (pass) and **140 s → `turn_budget_exceeded`** (fail). The fast path is
real (`reply generation: 14.1s`); the slow path is this one, and it is now
narrowed to a single, named place rather than "the turn is slow".

## Round 6, continued — the connect gap, and the answer's own cost

**3. The stream CONNECT is now bounded** (`_stream_connect_timeout_seconds`,
default 30, `ATOM_STREAM_CONNECT_TIMEOUT_SECONDS`). This was the hole both
earlier bounds fell through: the idle watchdog covers a stream that OPENS and
then goes quiet, and the orchestrator's first-visible deadline only sees chunks
— neither can act while the initial `create()` await is blocked, and that await
is bounded only by the SDK's own read timeout (120 s). Measured shape:

    INFO: Attempting stream with provider: openrouter … model=z-ai/glm-5.3-flash
    (115 s later)
    WARNING: chat reply generation timed out on the turn budget (115s)
    INFO: [stage-timing] reply generation: 115.0s

A provider that accepts the request and never answers consumed the whole turn
with nothing to decide on.

**4. The derivation answer is asked for in a compact shape** — the chain and
nothing else, one line per step, no preamble/restatement/closing offer. The
previous framing produced ~3000-char essays; measured output dropped to
**312–604 chars**. (Latency did not fall proportionally: the time is in the
stream/provider attempts, not in token generation — so this is a cost and
readability win, not the latency fix it was meant to be.)

## Where round 6 leaves the derivation

| run | route | chain | latency | outcome |
|---|---|---|---|---|
| 1 | openrouter/openai/gpt-5-mini | **yes** | 123 s | pass |
| 2 | openrouter/deepseek/deepseek-v4-pro | **yes** | **79 s** | pass (inside budget) |
| 3 | openrouter/deepseek/deepseek-v4-flash-0731 | no | 229 s | pass-through, no chain |
| 4 | (scored case) | — | 128.5 s | `turn_budget_exceeded` |

Planning is out of the variance (`canvas-edit 12.0 s`, `canvas-action 12.0 s`).
What remains is the reply/provider leg (57–115 s under load) on a host shared
with another application and several agent sessions (load average 12–19), plus
models that decline to use delivered evidence (`deepseek-v4-flash-0731`) while
others use it (`gpt-5-mini`, `deepseek-v4-pro`, `glm-5.3-flash` — each has
produced a full 6/6 chain at least once).

The honest summary: **the derivation succeeds with verifiable workbook evidence
and has fit the request budget at 79 s; it does not fit it reliably on this
host.** The remaining levers are the budget owner's call.

---

# Addendum — goal round 7 (2026-09-16 16:57–17:25 EDT)

## The carrier evidence now STATES the direction

Measured failure: asked *"which emails did WE SEND that carried X"*, the reply
called the carrier **"an inbound email from chandrakant to me"** while the
acceptance criterion — which derives direction from the addresses — read the
same message as **sent by this mailbox**. The two disagreed about a fact the
evidence block never stated, so the model inferred it.

`_messages_carrying_file` now annotates every carrier line:

    | DIRECTION: internal — both ends on brennan.ca; neither an inbound
      customer message nor a send to a counterparty

(or `crosses domains — the operator's own address decides who sent it`). Both
ends on one domain is a fact readable straight off the row; saying it removes
the ambiguity rather than picking a side.

Verified end to end on the live canvas (89 s, `z-ai/glm-5.3-flash`):

> "Short answer: none that we sent — the only message in the mailbox carrying
> **PRICE VIPEL (6).xlsx** is internal, and it came *to* Rish, not from him:
> From chandrakant@brennan.ca → To rish@brennan.ca … Both addresses are on
> brennan.ca, so it's an internal forward"

Tests: `TestCarrierLineStatesDirection` (2) — internal is labelled internal, a
cross-domain carrier is not.

## One clean single-instance acceptance run (no restart, low load)

| case | verdict | route | latency |
|---|---|---|---|
| quote | **PASS** (2 messages identified, attribution corroborated, quoted terms verified) | z-ai/glm-5.3-flash | 187.9 s |
| directional | FAIL (carrier not referenced) | deepseek/deepseek-v4-flash-0731 | 66.9 s |
| derivation | NOT_EVALUATED — `turn_budget_exceeded` | — | 128.6 s |
| control_unrelated_source | **PASS** | deepseek/deepseek-v4-flash-0731 | 129.6 s |
| control_missing_evidence | **PASS** | deepseek/deepseek-v4-flash-0731 | 86.1 s |

**3/5**, every case attributed to `cf766a4110bf-dirty.226fff9eede0.22345…`.

## The pattern that now explains this case set

Across every run this session the outcome tracks the MODEL, with byte-identical
delivered evidence:

* **use the evidence**: `openai/gpt-5-mini`, `z-ai/glm-5.3-flash`,
  `deepseek/deepseek-v4-pro` — each has produced a full 6/6 derivation chain or
  a correct carrier answer;
* **decline it**: `deepseek/deepseek-v4-flash-0731` — "the document lookup
  didn't return its data", a promise to search, or a question instead of the
  answer, repeatedly, with `[evidence] derivation block delivered to the model:
  … framing=True | row235=True` in the log.

That is a routing decision, and the brief forbids settling it by pinning a
model. The principled route is the one the objective already names: **let
observed outcomes steer the choice**. The deterministic detector already
exists — `_derivation_reply_ignored_the_row` knows when a reply ignored
delivered evidence — so recording that as a per-model verdict
(`evidence_ignored`) would give the learning router the signal, exactly as
`unsupported_figures` does for fabrication. That is the next step, and it is a
feature rather than a patch.

---

# Round 8 — the observation that was missing, and what the reply leg was really spending its time on

Round 7 ended with the case set reduced to one observation: **the outcome tracks
the model with byte-identical delivered evidence**, and the brief forbids
settling that by pinning a model. Round 8 builds the observation, then follows
the latency evidence wherever it led — which turned out to be *past* the reply.

## 1. `evidence_ignored` — the deterministic verdict, recorded per ROUTE

`_derivation_reply_ignored_the_row` already knew the fact: the delivered block
carried the matched row and its formulas, and the reply cited no row. Nothing
recorded it, so no router could learn from it.

* `core/llm/response_quality.py` — new signal, its own class: issue
  `evidence_ignored`, score **0.25** (above the fabrication band at 0.15 so it is
  never read as an outage-or-invention; below a refusal at 0.4 because the model
  contradicts its own prompt), `quality_satisfied=False`.
* `core/llm/fabrication_accounting.py` — `EVIDENCE_VERDICTS`, a first-class
  counter, and its **own denominator**. The fabrication denominator is
  `fabricated + grounded_ok` and decides the safety bench; letting a compliance
  failure enlarge it would rebuild exactly the dilution this module was written
  to prevent (1 fabrication + 1 ignored-evidence generation must read 1.0, not
  0.5 — asserted).
* `core/llm/learning_router_registry.py` — `record_evidence_ignored(...)`,
  joined to the generation that produced the reply, so the ledger stays one row
  per generation and repeats are idempotent.
* **Route attribution.** `RoutingFeedback.provider_id` and
  `prompt_features["route_provider"]` — model identifiers are not globally
  unique (an OpenRouter id carries a vendor namespace), so a per-route judgement
  needs both halves.
* **One verdict slot, ordered by severity**: an invention outranks ignored
  evidence, which outranks the marker that the grounding check merely ran
  (`VERDICT_PRECEDENCE`, `verdict_rank`). The old pairwise checks left the new
  middle class unguarded, so a later `grounding_ok` could have erased it.

Live, on the first turn that tripped it:

```
[derivation] reply ignored the delivered workbook row — grounded regeneration
[LearningRouter] evidence ignored by openrouter/z-ai/glm-5.3-flash
                 (question_answering): delivered evidence was not used
```

The row landed as designed: `score=0.25, quality_satisfied=0`,
`verdict=evidence_ignored`, `route_provider=openrouter`.

## 2. The corrective retry goes to a DIFFERENT route

Recording was only half of it: the regeneration used to re-send the same prompt
to the same route that had just ignored it. `_cross_route_retry_route` picks the
replacement from **the same ranked ladder the dispatch used** (never a literal
model) and prefers a different model on a different provider, then a different
model on the same provider, then the same model elsewhere; `None` when the
ranking offers nothing else, which keeps the current route — honest degradation
instead of a fabricated fallback. Both legs (streaming and the common post-reply
chain) do it, still through `_guarded_regen`, so it can never exceed the turn
budget.

```
[derivation] corrective retry on a different route: opencode-go/gpt-5.3-codex-spark
             (the route that ignored the row was openrouter/z-ai/glm-5.3-flash)
```

## 3. Two defects the live runs exposed in this new machinery — fixed the same round

**(a) The guard fired on non-derivation asks.** Case 2 of the acceptance run is
the *directional* ask, and its evidence carried the ingested workbook text with
the formulas marker (`ask=False matched-row-evidence=True`). The guard flagged a
reply that had answered the actual question correctly, and recorded
`evidence_ignored` against the model for it. The "did you cite the row"
requirement is only meaningful when the user asked for a derivation, so both the
verdict and the retry are now gated on `_is_derivation_ask`.

**(b) The guard fired TWICE per streamed turn.** The common post-reply guard
chain runs for streamed replies as well (its "non-streaming path" comment is
historical), so the corrective retry was dispatched a second time in the same
turn — visible in the log as two `reply ignored the delivered workbook row`
lines around `reply STREAMED`. The common-chain branch now requires
`_streamed is None`.

## 4. The fabrication bench was INERT — its key could never match

Found while giving the new verdict a consumer. `_fabrication_benched` queried
`model_id == f"{provider_id}/{model_id}"`. Feedback rows carry the **provider's
own identifier**, and an OpenRouter id already contains a vendor namespace:

| query | rows matched |
|---|---|
| `model_id = 'openrouter/z-ai/glm-5.3-flash'` | **0** |
| `model_id = 'z-ai/glm-5.3-flash'` | **667** |

So the safety exclusion had never fired for any gateway-served model, while
7/19 of that model's evaluated generations in the 48 h window carried
fabrication verdicts (and `openai/gpt-5-mini`: 20/55). The rows *were* there; the
key was not. The bench now matches the stored identifier and attributes the row
to the asking provider through the `route_provider` stamp.

**But the verdicts themselves were partly unsound.** Giving each verdict the
rule that produced it (`verdict_rule` in the ledger) and requiring a known-good
rule before it may EXCLUDE a route:

* the deterministic figure check reports "figures in the reply appear in NO
  retrieved evidence" — and for a derivation turn every correctly COMPUTED value
  is absent from the evidence text by construction. The live log shows exactly
  that: `[figure-grounding] reply states figures the evidence does not contain:
  5,625.30, 7,518, 1,893.70` on replies that had walked the stored formulas;
* 27 such rows exist across `z-ai/glm-5.3-flash` (7) and `openai/gpt-5-mini`
  (20), all written before the derivation-context suppression existed;
* they stay in the ledger (the accounting still reads them as fabrications) but
  they are **UNKNOWN CONTEXT** and cannot exclude a route — the mirror image of
  "no provenance is not clean": *unknown ruleness is not guilt*.
* New verdicts are withheld entirely when the delivered evidence carried the
  matched row's formulas (`_figures_derivable`), and are stamped
  `figures_v2` / `panel_v1` when written.

Measured effect of the key fix, before and after the rule requirement:

| pair | with the key fix only | final (rule-gated) |
|---|---|---|
| `openrouter/z-ai/glm-5.3-flash` | benched (7/19) | not benched |
| `openrouter/openai/gpt-5-mini` | benched (20/55) | not benched |

Benching them on that evidence would have removed the two models that had
produced the correct derivation chains *because a rule found correct arithmetic
"suspicious"* — the manufactured-observation failure, inverted.

## 5. Where the reply leg's time actually went: the verification panel

The brief asked for the 118.5-second control to be investigated against the
intended turn budget rather than treated as irrelevant. It is not the reply. On
one derivation turn the reply was **STREAMED in 5.6 s** and the reply leg
finished in **9.6 s**, while the POST returned after **180.0 s**. The difference
was the verification panel: it runs AFTER the reply exists, it was unbounded,
and its judge samples walked a ladder of routes that each truncated
(`Structured attempt failed for openrouter/…: The output is incomplete due to a
max_tokens length limit.`).

Two fixes, both bounded and testable:

* **`_bounded_verify`** wraps every panel call in the turn budget, and the panel
  gets its **own hard cap** (`ATOM_VERIFY_PANEL_MAX_SECONDS`, default 30 s).
  Bounded only by the turn it consumed whatever was left and *then* timed out:
  measured on the 8004 run, reply at 21.1 s, panel timeout at the budget,
  response at 95.5 s — ~74 s spent buying no verdict. `ran=False` is the
  contract's existing "verification unavailable": never "verified", never a turn
  failure.
* **SC fan-out ranking was dead**: every fan-out logged
  `SC fan-out: ranking failed (BYOKHandler.get_ranked_providers() missing 1
  required positional argument: 'complexity'); samples unpinned`. The voter
  called a signature that requires the complexity, so the diversity pins never
  engaged; the broad `except` made a degraded path look like a working one. The
  complexity is now derived from the prompt with the handler's own analyzer.

## 6. Derivation-scoped reply levers

Two levers keyed to `_is_derivation_ask`, both resolved per call so an operator
can change them without a restart:

* first-visible deadline **15 s** (instead of 30 s): a derivation answer is a
  short transcription, so silence means hidden thinking is eating the turn;
* completion cap **3000** (`ATOM_DERIVATION_COMPLETION_MAX_TOKENS`): `max_tokens`
  also sets the hidden-reasoning budget (a third of the cap), and an
  over-generous cap lets a reasoning-heavy route think ~2000 tokens and then
  truncate with nothing visible — the second half of the failure below.

## 7. Measured, on frozen trees

Verification ran against **frozen worktrees** (`/tmp/atom-r8-verify`: clean
`cf766a4110bf` + the round-8 files), served on a dedicated port through a shim
module so the concurrent session's `pkill -f "uvicorn main_api_app:app"` could
not kill it mid-run — which it did twice before (one full acceptance run died
with four transport errors).

**Derivation-only run** (`cf766a4110bf-dirty.af8586830a60`, single instance):
**PASS** — workbook named, row 235 identified with the listed 7519, sheet
`Sheet1`, **6/6 chain steps**, no fabricated chain, **12 asserted equalities
verified against the workbook store**, unresolved `O235` reported. 180.0 s —
and that 180 s is what located the panel (the reply itself was 9.6 s).

**Full five-case runs** — three runs on frozen trees, single instance each, no
restart (A: panel bounded by the turn; B: panel hard cap; D: every post-reply
regeneration bounded):

| case | run A (`…123253d76391`) | run B (`…cd57af5a5b2a`) | run D (`…efe192834a75`) |
|---|---|---|---|
| quote | **PASS** 95.5 s | **PASS** 82.3 s | **PASS** 76.8 s |
| directional | **PASS** 153.5 s | **PASS** 84.6 s | **PASS** 95.1 s |
| derivation | NOT_EVALUATED 115.0 s | **EVALUATED** 105.0 s — quality FAIL | **EVALUATED** 230.2 s — quality FAIL |
| control_unrelated_source | **PASS** 95.1 s | FAIL 86.0 s | **PASS** 62.5 s |
| control_missing_evidence | **PASS** 35.3 s | **PASS** 67.7 s | **PASS** 59.6 s |
| total | 4/5 | 3/5 | **4/5** |

Run A: **4/5** and every failure is delivery-side. Run B: **3/5**, and the
change of shape is the point — the derivation is finally **evaluated inside the
budget**, and what it fails on is the ANSWER:

```
M235 = L235/0.86 = 6465.862068965517/0.86 = 7515.650080   ← store: 7518.444266238974
N235 = ROUNDUP(7515.650080,0) = 751                        ← store: 7519
```

`derivation.no_fabricated_chain`, `derivation.values_match_store` (2 asserted
values contradict row 235) and `derivation.unresolved_reported` fail on that
arithmetic; the workbook, row, sheet and the other four chain steps are right.
No failure mode is hidden behind "the case could not run" any more.

**A finding this exposed (owner: the concurrent session's derivation verifier).**
That turn logged

```
[derivation-verify] claims=3 checked=2 contradicted=0 unresolved=1
                    → unverified — dependencies outside the delivered window: P235
[figure-grounding] skipped: every anchored claim was verified against the workbook's own formulas
```

so the wrong `7515.650080`/`751` passed the verifier and, through
`_figures_derivable`, suppressed the figure check — while the acceptance
instrument independently caught both values. Two independent checks disagree,
and the composite gate is only as strong as the verifier. The suppression stays
as configured (requiring *complete* verification would re-run the
evidence-absence check on correct uncited chains and re-create the false
verdicts of §4), so the fix belongs in the verifier: a claim whose asserted value
disagrees with the evaluated formula must land in `contradicted`.

**The rule stamp had to encode the CONTEXT, not the code version.** One stamped
`figures_v2` verdict recorded on the shared instance flagged `$4,815.00` — a
value stored in the workbook row — on a reply with no derivation cross-check.
So the stamp now distinguishes proof from heuristic: a workbook-CONTRADICTED
verdict may exclude a route (`figures_v2`), an evidence-absence verdict may not
(`figures_heuristic`, recorded but never bench-eligible). Same rows, different
rule, different outcome — asserted end to end through the bench.

**Run D, and the last unbounded leg.** Run D's other four cases are the
strongest of the series (76.8 / 95.1 / 62.5 / 59.6 s), and the directional case
passed ON `deepseek/deepseek-v4-flash-0731` — the model that declines when the
evidence is wrong is not a model that always declines. The derivation turn,
however, took **230.2 s**, and the turn's own deadline instrumentation shows why:

```
[deadline] chat-request stage=reply-leg dur=84.2s turn_offset=20.9s
           elapsed=105.1s remaining=9.9s budget=115.0s
[derivation] corrective retry on a different route: opencode-go/gemini-3-flash
WARNING: Attempt failed for opencode-go/gemini-3-flash: 401 AuthError
[verify-panel] skipped — turn budget exhausted
[verify-panel] corrective regeneration skipped (turn budget)
[verify-panel] skipped: the reply ships unverified rather than late
RuntimeWarning: coroutine 'verify_reply' was never awaited
[intent] using tool-plan routing fields: search_request (conf=0.90)
Routing to features: [SEARCH, AI_ANALYTICS]          ← +120 s, unbounded
```

Every bounded stage did its job — the reply leg stopped at 105.1 s of a 115 s
budget, the corrective retry got the remaining 9.9 s and died on a 401, both
panel calls were skipped. What then took the turn to 230 s is the **legacy
intent-router path**: the reply leg returned nothing usable (`_content` empty
after the firm protocol-syntax retry), `_get_qwen_response` returned `None`, and
the orchestrator's fallback ran the legacy SEARCH + AI_ANALYTICS handlers, which
make their own unbounded LLM calls. That is the last unbounded leg in the reply
path and the next round's first item.

Two defects this run also exposed and fixed: a skipped panel left a
never-awaited coroutine (`_coro.close()` now, with a test), and every remaining
post-reply corrective regeneration (six sites in the common guard chain:
inability, capability-honesty, non-responsive, evidence, identity, figure)
was a bare `await` — all six now go through `_guarded_regen`, so no advisory
rewrite can extend a turn past its budget.

**Latency, measured:** the reply leg is no longer the long pole. Across run B the
panel is capped (`[verify-panel] timed out on the turn budget — the reply ships
unverified rather than late`) and case latencies are 35–105 s against 95–187 s
in run A; the derivation — 128.6 s NOT_EVALUATED in round 7 and 115.0 s
NOT_EVALUATED in run A — is delivered at 105.0 s here. One panel call did
complete inside the cap: `[verify-panel] enforce: grounded=True agreement=1.0
(high, 1 samples, 23.4 s)`.

**Tests** (frozen tree): **257 passed** across the ten affected suites —
`test_evidence_ignored_verdict.py` (34, new), `test_reply_leg_bounds.py` (20,
new), `test_fabrication_accounting.py` (43), `test_derivation_lane_independence.py`,
`test_model_route_identity.py`, `test_acceptance_criteria.py`,
`test_independent_corpus_api_boundary.py`, `test_attachment_carrier_ranking.py`,
`test_named_file_probe.py`, `test_stream_connect_bound.py`.
`check_undefined_names.py`: clean.

## Still open after round 8 (each with its evidence)

1. **The legacy intent-router fallback is unbounded** and becomes the critical
   path whenever the reply leg returns nothing usable: run D spent 105.1 s of a
   115 s budget and then ~120 s more there (`Routing to features: [SEARCH,
   AI_ANALYTICS]`). It needs the same treatment the reply leg got — one deadline
   for the whole request.
2. **The derivation verifier can miss a contradiction** (claims=3 checked=2
   contradicted=0 on a chain that asserted `7515.650080` where the workbook
   holds `7518.444266238974`), and because `_figures_derivable` trusts it, the
   figure check is then suppressed on a wrong answer. The acceptance instrument
   caught both values independently; the verifier did not.
3. **Derivation QUALITY is the remaining case failure**, and it tracks the
   route: `deepseek/deepseek-v4-flash-0731` produced 0/6 chain steps with
   fabricated intermediates (run D), while `z-ai/glm-5.3-flash` and
   `openai/gpt-5-mini` produced 6/6 chains (runs B and the derivation-only run,
   the latter with 12 asserted equalities verified against the workbook). The
   observation machinery for this is now live (`evidence_ignored`, per route);
   what it needs is *repeated real turns* before it can move the ranking, and
   the acceptance set alone gives each model one turn per run.
4. **`control_unrelated_source` is intermittent** (FAIL in run B, PASS in A and
   D) — the same "named source neither verified nor disclaimed" mode the round-6
   note describes; it is sensitive to whether the planner's search produces a
   store hit for the named file.
5. `opencode-go` still 401s on completions with an active key (run D: the
   corrective retry's chosen route), so a cross-provider retry can pick a
   provider whose credential is broken; the auth memo benches the pair, but the
   pre-computed fallback ladder does not reflect it.

---

# Rounds 9–10 — the request budget reaches the LAST unbounded legs

Round 8 ended with four of five acceptance cases passing on a frozen build and
one located failure: the derivation was *evaluated* but its answer was wrong,
and one run had spent 230 s doing it. Rounds 9–10 close the budget question —
the reply path now has ONE clock that every leg spends from — and the derivation
case passes.

## 9. The legacy intent-router fallback was outside the budget

Run D's evidence (`…efe192834a75`): the reply leg stopped correctly at 105.1 s of
a 115 s request budget, every bounded stage skipped as designed — and the turn
then returned at **230.2 s**, because the path that handles "the reply leg
produced nothing usable" runs an NLU completion and then one or more feature
handlers, none of them aware of the request's clock:

```
[deadline] chat-request stage=reply-leg … elapsed=105.1s remaining=9.9s budget=115.0s
[verify-panel] skipped — turn budget exhausted
[intent] using tool-plan routing fields: search_request (conf=0.90)
Routing to features: [SEARCH, AI_ANALYTICS]        ← +120 s, unbounded
```

The fix is a gate, not a timeout: the fallback (NLU + feature routing) starts
only when at least `_LEGACY_TAIL_RESERVE_SECONDS` (12 s) of the request remains —
enough to assemble, persist and serialize the answer. When it does run, feature
routing is bounded by `_deadline.slice(_FEATURE_ROUTING_MAX_SECONDS)` (45 s) and
a timeout continues without it; the LLM-free `_fallback_intent_analysis` replaces
the NLU completion when the clock is short. A skipped fallback is reported the
way the objective requires — **failed delivery, quality NOT evaluated**:
`error_code=turn_budget_exceeded`, a `failure_reason` naming the stage, and a
`deadline` block with elapsed/remaining — and no durable "fact" is extracted from
the canned template text that would otherwise have been returned as an answer.

Measured effect (round-9 run, `…3319b40f2ca7`): the same situation now ends at
**95.0 s** with `[deadline] legacy fallback skipped: the reply leg produced no
usable answer and only -0.0s of the request budget remained`.

**Every reply-leg generation is now bounded.** The last two bare `await`s — the
protocol-syntax firm retry (the one that leaves `_content` empty and hands the
turn to the fallback) and the non-streaming derivation retry — go through
`_guarded_regen`, so no advisory rewrite can extend a turn past its budget.

## 10. The pre-reply legs could eat the reply leg's share

Round 9's acceptance finally passed the derivation — and lost a control case to
the *other* end of the same problem:

```
[timeline] chat planner finished: 31.8s after the turn's canvas-edit clock started
[stage-timing] canvas-edit plan: 54.7s
[deadline] chat-request stage=reply-leg-START turn_offset=56.2s elapsed=56.2s remaining=38.8s budget=95.0s
[stage-timing] reply generation: 38.8s
WARNING: chat reply generation timed out on the turn budget (39s) — returning a structured error
```

A control question spent 54.7 s in the canvas-edit leg (bounded at 12 s only for
*derivation* asks) and left the reply leg 38.8 s. Both canvas legs are now
bounded for every request class and reserve the reply leg's share:
`_pre_reply_leg_timeout(deadline, want) = deadline.slice(want, reserve=_REPLY_LEG_MIN_SECONDS)`
(general cap 45 s, reply-leg reserve 40 s), and a leg with no affordable time
left is **skipped and says so** rather than started.

## Measured across the two rounds (frozen trees, single instance, no restart)

| case | round-8 run D | round-9 (`…3319b40f2ca7`) | round-10 (`…526ddeb41cf9`) |
|---|---|---|---|
| quote | PASS 76.8 s | PASS 95.5 s | see run below |
| directional | PASS 95.1 s | PASS 75.8 s | |
| **derivation** | FAIL 230.2 s (0/6 chain) | **PASS 60.3 s — 6/6 chain, 9 verified equalities** | |
| control_unrelated_source | PASS 62.5 s | NOT_EVALUATED 95.0 s (`turn_budget_exceeded`, stated) | |
| control_missing_evidence | PASS 59.6 s | PASS 31.7 s | |

The derivation criterion of the objective — *"derivation succeeds through the
canvas with verifiable workbook evidence"* — is met on this build, with the
acceptance's independent workbook read-back confirming the chain (workbook, row,
product, sheet, 6/6 steps, every asserted figure traced to a stored value, the
unresolved cell reported). The one non-passing case is a *stated* delivery
failure, not a silent or late answer, which is what item 5 asks for.

**A live regression caught while working on round 10:** the working tree briefly
carried `_reply_token_cap()` without its lazy import of
`_DEFAULT_COMPLETION_MAX_TOKENS` (a `NameError` on every reply leg —
`check_undefined_names.py` flagged it, the import is restored, and the checker
exists precisely for this class).

**Tests:** 271 passed across the eleven affected suites, including the new
`tests/test_legacy_fallback_deadline.py` (12) and the re-contracted canvas-bound
tests.

**One pre-existing failure, reproduced on a pristine HEAD worktree**
(`/tmp/atom-head`, c31316004) so it is not chased as a regression:
`tests/test_r83_evidence_defaults.py::TestSoftSCGatewayRejection::test_logprobs_rejection_retries_without_logprobs`
— the code deliberately matches `"logprobs are not supported"` while the test's
fake raises `TypeError("unexpected keyword 'logprobs'")`.
