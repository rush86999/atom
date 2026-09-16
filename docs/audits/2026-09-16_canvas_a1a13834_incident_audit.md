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

> ### ⚠️ CORRECTIONS — 2026-09-16 independent verification pass
>
> The root causes below held up under reproduction. Four claims did not, and
> are corrected in place by
> [`2026-09-16_verification_and_corrections.md`](2026-09-16_verification_and_corrections.md)
> (full matrix, reproductions and remaining limitations):
>
> 1. **§2.5 RC-18 / §3 — the app-DB allowlist was not a boundary.** A
>    predicate-only read of a non-allowlisted table returned rows
>    (`SELECT id FROM canvases WHERE (SELECT count(*) FROM 'users') > 0`), as
>    did the `EXISTS (SELECT 1 FROM (SELECT * FROM 'user_sessions') canvases)`
>    variant: both the validator and the result-column check are blind to a
>    table read that is never projected. Closed with a SQLite authorizer; the
>    timeout now also calls `Connection.interrupt()` so the caller's wait
>    ending genuinely stops the database work.
> 2. **§3 — "headers/SQL/formulas always surviving" the evidence budget was
>    false.** `SQL RESULT` and `FORMULAS` lines were elidable body lines.
>    Fixed and pinned by `TestBudgetPreservesDecisiveLines`.
> 3. **§5.4 — "~90 verdict rows" was not a representative sample.** Accrual was
>    dead from `9a4a2a774` until `76cc51bcd`; every row postdates 2026-09-15
>    22:24 UTC and 8 synthetic `probe/*` rows had been purged. Current:
>    170 rows / 168 distinct generations / 14.2 h. The 30-row rule shows
>    **readiness, not superiority** — no executed comparison against static
>    BPC exists, and an unexecuted alternative has no outcome.
> 4. **§5.1 — "an infrastructure spend decision, not a code fix" is not
>    supported.** The routing ladder returned 9/9 candidates from a single
>    provider (`openrouter`) with every fallback sharing it, because all 5 keys
>    in `data/byok_keys.json` are tenant-prefixed while `get_api_key` built the
>    unprefixed id — the whole local key store was unreachable at runtime.
>    Fixed; the same live configuration now yields **118 candidates across 3
>    providers** (`deepseek`, `openrouter`, `opencode-go`). No purchase is
>    justified by the evidence.
>
> Also corrected: `record_fabrication_signal` wrote **two** feedback rows per
> verdict (one with provenance, one without), inflating the bench denominator;
> it now writes one, with provenance.
>
> **This banner SUPERSEDES the body wherever they disagree.** Sections 3, 5
> and 7 below were written mid-incident and describe intentions, not the
> current state; treat every claim in them as superseded unless it is restated
> in the status block.

---

## 0. Current status — one consistent account

> **Status: OPEN.** Updated 2026-09-16 by the stabilization pass, superseding
> earlier per-round claims in this section. `docs/audits/2026-09-16_workbook_derivation_round.md`
> is the newer chronology and wins on routing detail (§0.1 reconciles the run
> counts).

### 0.1 The single coherent acceptance result

The only run that counts as a coherent measurement is one instance, one build,
no restart, low load:

| case | verdict | latency |
|---|---|---|
| quote | PASS | **187.9 s** |
| directional | FAIL (carrier not referenced) | 66.9 s |
| derivation | **NOT EVALUATED** — `turn_budget_exceeded` | 128.6 s |
| control_unrelated_source | PASS | 129.6 s |
| control_missing_evidence | PASS | 86.1 s |

**3/5 on `cf766a4110bf-dirty`.** Completion therefore requires grounded answers,
bounded delivery AND correct evaluation — not another isolated successful
derivation.

**Reconciling the conflicting counts.** Earlier entries in this section and in
the round log cite 2/5, 4/5 and "all five have passed". All three are true of
*older builds or multi-instance sweeps*, and none is an acceptance result:

* the **4/5** run was against a build that has since changed, and its
  derivation case is the one now failing on budget;
* **"all five have passed"** aggregates cases passed on *different* builds and
  must not be read as a suite result — no single build has ever passed 5/5;
* the **2/5** run was confounded by a concurrent restart.

**Timing is a first-class verdict, not a footnote.** The quote case PASSED at
187.9 s against a ~115 s internal budget and a 120 s client abort: that is a
**quality pass and an operational failure**. A 209 s response cannot satisfy a
115 s budget regardless of answer quality, so latency and correctness are
reported separately from here on and a pass that breaches the deadline is
recorded as a breach.

### 0.1b VALID frozen-build run (2026-09-16, supersedes 0.1 as the current number)

One instance, one frozen build, **no restart mid-run, 0 not-evaluated** — the
first run of this incident where every case was actually evaluated:

| case | verdict | latency | vs 0.1 |
|---|---|---|---|
| quote | PASS | **62.5 s** | was PASS at 187.9 s |
| directional | PASS | 56.9 s | was FAIL |
| derivation | **FAIL** (quality) | 71.6 s | was NOT_EVALUATED at 128.6 s |
| control_unrelated_source | FAIL | 54.8 s | was PASS |
| control_missing_evidence | PASS | 73.8 s | was PASS |

**3/5, every case inside the 95 s budget, zero deadline breaches** — against
0.1's run where the passing case took 187.9 s and one case breached.

**Two findings that change the picture:**

1. **A measurement confound, now removed.** The earlier 187–265 s latencies (and
   the directional failure) were taken with a staging instance pointed at a
   **stale 215-row memory store** instead of the live 7,391-row store. With the
   real stores linked, the same cases run 55–74 s. Some of what was attributed to
   host load and model choice was a depleted fixture: the pipeline worked harder
   to find nothing. Latency conclusions drawn before this are not trustworthy,
   and directive 2's warning about inferring cause from correlation applies to
   the earlier reports as much as to any new experiment.
2. **The derivation case now completes inside budget and fails on QUALITY, not
   timing.** It resolves the right workbook, row 235, the listed value, and every
   asserted equality, and introduces **no fabricated figures** — but states 4 of
   6 chain steps, missing the `/0.86` dealer-margin step and the ROUNDUP that
   produces the listed price. That is a substantive answer defect and the next
   thing to fix; it is no longer an operational failure.

**Where the time goes** (from `[deadline]` traces on this run): the reply leg
starts at a **turn offset of 33.0 s of a 95 s budget** and takes 22.2 s
(`remaining=39.8s`). Planning is therefore ~35% of the critical path — the
largest single consumer, and where the next latency work belongs.


| Directive | Change | Evidence |
|---|---|---|
| 1 · one deadline | `TurnDeadline` established as the **first statement of the request** and threaded into the reply leg. Per-leg constants are now upper bounds (`deadline.slice`), the first-visible bound is capped to the remaining time, and the reply leg refuses to start when the turn is already out of time. | **[I][T]** 113 passed across six suites |
| 1 · cancellation | `_cancel_and_confirm` cancels the turn's owned tasks, waits a grace window and **reports survivors** — cancelling a coroutine awaiting a provider read does not stop the work behind it. | **[T]** probe correctly reported `survived: 1` for a task that ignores `CancelledError` |
| 3 · verification | The citation bypass is **removed**. Claims are checked by **evaluating** the workbook's own formulas: STORED / COMPUTED / UNRESOLVED / CONTRADICTED, with `is_clean` requiring that something was actually checked. `COLUMNS: <name>=<letter>` now bridges rendered column names to the letters formulas use. | **[I][T]** 16 new tests; the five required cases behave correctly |
| 4 · detector | `_derivation_reply_ignored_the_row` is **NOT** promoted to a model-quality verdict in this pass (see §0.3). | — |

### 0.3 Correction to the round log's "next step"

`2026-09-16_workbook_derivation_round.md` concludes that recording
`evidence_ignored` from `_derivation_reply_ignored_the_row` is "the next step".
**That is wrong as written and is not being done.** The detector infers "the
reply ignored the evidence" from the ABSENCE of a row-reference pattern, which
is not proof of anything: a correct calculation can omit the citation syntax
(the verification contract above explicitly classifies such an answer as
UNVERIFIED, not failed), and a useless answer can include it. Before it can
influence routing it must establish that the dispatched prompt actually carried
sufficient relevant evidence AND that the answer failed the requested task —
distinguishing missing citation, unanswered request, justified uncertainty,
unavailable evidence and incorrect calculation. It stays on the observation /
shadow path until that behaviour is established.


**Revision (this table's measurements):** `010b70d40` · **Serving process at
the time:** pid **22091**, started **2026-09-16T14:01:51Z**, port **8001**, db
`backend/data/atom.db`.

> The per-area table below is a HISTORICAL record of what each round established.
> It is **not** the current acceptance status — that is §0.1. Its revision and
> pid are pinned to the round that produced it, and the code has moved since
> (the stabilization pass in §0.2 landed on top of it). Read a row as "this was
> implemented and tested at that revision", never as "this is green now".
**UI attribution (verified, not assumed):** the Next.js app on :3000 proxies
`/api/*` to **8001**, and the browser held **3 established sockets to 8001 and
0 to 8000**. Port **8000 is a DIFFERENT application** (`atom-saas/backend-saas`,
commit `7ced86ffa3`, started Sep 6) — earlier notes calling it "a stale Atom
instance" were wrong.

Evidence grades used below:
**[I]** implemented · **[T]** tested in isolation · **[V]** verified through the
serving API/UI.

| Area | Superseded claim | Current state |
|---|---|---|
| App-DB SQL boundary (§2.5 RC-18, §3) | "a completed app-DB NL→SQL with a table allowlist" | **[I][T]** SQLite authorizer is the authoritative boundary; 15/15 attack + 5/5 inference scripts contained; timeout calls `Connection.interrupt()`. **[V]** not yet re-run against the serving process |
| Evidence budget (§3) | "headers/SQL/formulas always surviving" | **[I][T]** decisive-line preservation pinned; token accounting added (18k chars = 4,510–8,208 tokens by content shape); `relevant_window` now character-centred with containment enforced |
| Provider availability (§5.1) | "infrastructure spend decision, not a code fix" | **[I][T][V]** the local key store was unreachable (tenant-prefixed ids vs unprefixed lookup); fixed, and the serving process logs `deepseek`, `opencode-go`, `openrouter` BYOK clients. Ladder 9 candidates/1 provider → 118/3 |
| Cache copying (§7 superseded note) | "probe results cached BY REFERENCE — read-only consumers" | **[I][T]** deep-copied on store and hit; identity-scoped keys; anonymous entries bypass the cache |
| Verdict accounting (§5.4) | "auto-active on ~90 verdict rows" | **[I][T]** accounting is per EVALUATED GENERATION; the denominator requires a fabrication verdict or an explicit `grounding_ok` marker (newly emitted); unprovenanced scores are `unevaluated`/`unknown`, never "clean" |
| Correction lifecycle (new) | — | **[I][T]** verdict is a first-class field (survives feature recovery); the annotated row's quality fields follow a fabrication verdict; in-memory learning supersedes rather than appends, so a restart cannot flip the router's view |
| Office-file ownership | "resolved" in the follow-up report | **[I][T]** containment holds, ownership does NOT: any authenticated user may name any file under a flat `ATOM_OFFICE_DIR`. Characterization tests pin it; the per-user migration is unowned and deferred (canvas rows persist these paths) |
| Legacy `.doc` | name-only in the store | **[I][T]** reported as `unsupported_format` + `extraction_supported: False` instead of `no_text`; extraction remains unsupported |

### Measurement inventory — the two reliability scripts are not interchangeable

The audit referenced both; they measure different things, and their numbers
must not be compared or combined.

| Script | Artifacts | What it actually measures |
|---|---|---|
| `backend/scripts/measure_provider_reliability.py` | `scripts/provider_reliability_20260916_124{6,7,8}.json` | 6 bounded attempts: a planning **structured** call plus a short **streaming** answer. Records **streamed time-to-first-visible**, fallback engagement, 429s, cost. Runs `1246`/`1247` are harness failures (6/6 exceptions: `AttributeError: 'BYOKHandler' object has no attribute 'generate_completion'`, then `NameError: name 'svc' is not defined` + `ImportError: get_fallback_models`); **`1248` is the only valid run** (6/6 ok, median 12.5 s, TTFT median 13.4 s) |
| `backend/scripts/provider_reliability_replay.py` | `scripts/provider_reliability_live_20260916.{json,md}` | Three **prompt-size tiers** (small/medium/evidence-sized) via a **non-streaming** completion, plus the routing-topology check (candidate ladder, provider diversity, whether fallbacks share the primary's upstream) |

Three distinctions that the earlier report flattened:

1. **Streamed first-visible latency ≠ total latency.** `1248`'s 13.4 s TTFT is
   a streaming measurement; the replay's tier latencies are whole non-streaming
   completions. They are not the same quantity and neither is "the" latency.
2. **A non-empty response is not a correct grounded answer.** Both scripts
   score *non-empty*, and `provider_reliability_replay.py` classifies
   rate-limit / timeout / budget-exceeded separately. Neither establishes
   groundedness — that is what the grounding marker and fabrication verdicts
   are for, and they are a different channel.
3. **118 candidates across 3 providers is candidate AVAILABILITY only.** It is
   not proof of successful authentication (that needs a live provider
   round-trip — the concurrent session reports `/api/ai/providers/{p}/test`
   succeeding for all three against pid 11051; **I have not reproduced that
   myself**), not proof of a *usable independent fallback*, and not proof of
   incident recovery. A controlled cross-provider fallback was **not executed**
   in this pass.
4. **Benchmark traffic and production learning.** The extended replay script
   documents installing no-op learning hooks so benchmark attempts do not land
   in `llm_routing_feedback`. I read the intent and the call sites but did not
   independently verify the isolation by counting rows around a benchmark run.
5. **Disagreement logs do not supply outcomes.** A logged routing disagreement
   records what was *not* executed; it is not an observation of the
   alternative. And "twenty attempts" (or six) is a sampling choice, not an
   automatic trust threshold.


### Office-file ownership — contract, disposition, owner (inspection done, change NOT made)

**Inspected, not assumed:**

- `core/office_service._validate_office_path` contains a path to
  `ATOM_OFFICE_DIR` (one flat directory). `api/office_routes.py` carries
  router-level `Depends(get_current_user)`, so the effective rule today is
  *authenticated ⇒ install-wide access to every office file*.
- **Ownership is already derivable, so a filesystem move is not required.**
  Canvas content stores both `office_file` (absolute path) and `file_path`
  (relative) — verified in the live DB — and `canvases.created_by` exists. An
  office file's owner is therefore the owner of the canvas that references it.
- **The affected surface is small: 4 of 76 canvases** reference an office file
  at all. Canvas ownership in the live DB: 67 to the admin, then 6/1/1/1 to
  four other users, plus one legacy canvas owned by the non-UUID placeholder
  `u-58`.

**Intended authorization contract (proposed):**

1. An office file is reachable **iff** the caller owns — or is an admin over —
   a canvas whose `content.office_file` / `content.file_path` references it.
2. Read (`GET /excel`, `/word`, `/pptx`), export (`POST /present`) and mutation
   (`POST /excel`, `/sync-update`) all pass the same check. Today `present`
   and `sync-update` already carry `current_user`; the read endpoints do not
   use it.
3. **Legacy files with no referencing canvas resolve to admin-only**, not to
   "everyone". This is the ambiguous-ownership rule: fail closed, and log the
   path so an operator can adopt it onto a canvas.
4. A per-user subtree under `ATOM_OFFICE_DIR` stays **optional hardening** —
   useful for defence in depth, not a prerequisite, because the relation that
   decides access is already stored.

**Disposition: NOT implemented.** This narrows access to files that are
currently readable by every authenticated user, so it needs the operator's
decision rather than a silent change inside a verification pass.
**Owner:** the office/canvas surface — `api/office_routes.py` +
`core/office_service.py`, with the canvas relation read via
`canvases.content.office_file`. `tests/test_office_file_ownership_boundary.py`
pins the current behaviour, including the negative case, so implementing the
contract flips an assertion deliberately.


### Acceptance replay — executed against the serving canvas

`backend/scripts/acceptance_replay_canvas.py` replays the three original asks
plus two controls through `POST /api/chat/message` on the incident canvas
(`a1a13834-7bb3-4b3b-91cf-e83a2287daf0`), against the process the browser is
connected to, and records the serving process identity alongside every result.

**Serving process for the reported run:** pid **33683**, started
**2026-09-16T14:29:46Z**, port 8001, db `backend/data/atom.db`. The script now
re-reads the identity **per case**; this run was answered entirely by one
process, which is now provable rather than assumed.

⚠️ **An earlier run was confounded by a mid-run death.** pid **22091** answered
cases 1–3 and then died; cases 4–5 hit `RemoteProtocolError` / `ConnectError`
while the report still carried a single start-of-run identity. Attributing a
whole run to one process without re-checking is exactly the error this pass
exists to prevent — the per-case check was added because of it.

| # | Case | Result | Latency | Evidence |
|---|---|---|---|---|
| 1 | Original quotation lookup — `search for this one: $ 5,350.00 - 10 % in stock` | **PASS** | 49.4 s | `seguin`, `5,350`; also passed at 41.7 s and 133.4 s on earlier runs |
| 2 | Directional mail lookup — "which emails did we send that carried the PRICE VIPUL price list as an attachment?" | **PASS** | 96.8 s | `price vipul`, `attachment`, `email`, `sent` |
| 3 | Workbook derivation — "open PRICE VIPUL and show how the 7519 listed price was derived" | **FAIL — provider availability** | 34.7 s | `[Error: All LLM providers failed…]`. Passed once (32.3 s, matched `7,519`) and failed on three other attempts |
| 4 | CONTROL — quoted line that is not mail (workbook scorecard) | **PASS** | 176.7 s | `0.87`, `reliability`, `scorecard`, `workbook` |
| 5 | CONTROL — answer not in any store (`F-9999`) | **PASS on the merits** | 41.0 s | Reply: *"I don't have an F-9999 press in the records returned here… the only machine carrying it is a different model: PRICE VIPUL (6).xlsx, Sheet1, row 235, F-52\"x16G, LIST 7519.0"* — a disclaimer with correct attribution |

**On control 5 — a criterion gap, twice.** This case first failed because the
reply *mentioned* `$7,519`; corrected to forbid only a price **attributed to the
target**. It then failed again because the reply's disclaimer used *"I don't
have…"*, which the keyword list did not cover. Both were defects in the
acceptance criterion, not in the product; the reply is the honest behaviour the
incident demanded. Fixing the criterion changed the count, so it is recorded
rather than silently re-run.

**Verdict against the acceptance criterion (updated 2026-09-16 11:05, pid
33683):** 4 of 5 pass on the merits; the derivation case is **intermittent**.
Across five runs on this process the same derivation ask passed once (11.3 s)
and failed four times with `[Error: All LLM providers failed…]`. Control 5's
replies were correct every time; the criterion that rejected them was mine and
has been rewritten as a regex over the disclaimer's *shape* (an enumerated
keyword list failed open on "I don't have", then "I can't find").

Two distinct obstacles remain, and neither is the derivation logic:

1. **Provider availability / routing catalog** — the failing turns name model
   IDs the providers reject. Owner: BPC/routing.
2. **Serving-process latency** — observed turn times rose across the session
   (quotation lookup 41.7 → 49.4 → 117.9 s; unrelated-source control
   118.5 → 176.7 → 236.8 s), and the final control run exceeded a 240 s client
   timeout. The set is no longer completable within a reasonable window on this
   process.

The incident is therefore **not closed**: the two asks that originally failed
(quotation lookup, directional mail) pass consistently, but the third cannot be
met reliably.

**Root cause of the derivation failure — invalid model IDs in the candidate
ladder.** The server log for that turn shows BPC walking a fallback chain in
which *every* candidate is a model no configured provider accepts:

```
gpt-5.3-codex-spark                       → opencode-go 401 Invalid API key
                                          → openrouter 400 "not a valid model ID"
tencent/deepseek-v4-pro                   → opencode-go 401 "Model … not supported"
                                          → openrouter 400 "not a valid model ID"
fireworks_ai/accounts/fireworks/models/deepseek-v4-pro
                                          → opencode-go 401 "not supported"
                                          → openrouter 400 "not a valid model ID"
ERROR: All 3 providers failed for fireworks_ai/…/deepseek-v4-pro
```

This is the concrete form of the caveat recorded above: **118 candidates across
3 providers is candidate availability, not a usable fallback.** The ladder was
enumerated from a catalog whose IDs the providers reject, so "three providers"
bought nothing — the same upstream-shaped dead end as the single-provider
ladder, arrived at differently. Note also that `opencode-go` returns **401
Invalid API key for every model**, which is a credential problem distinct from
the invalid-ID problem and needs its own fix.

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
