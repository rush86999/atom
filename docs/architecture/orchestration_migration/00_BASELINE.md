# Orchestration Migration — Baseline (Discovery Artifact 0)

Status: discovery artifact, implementation-gated. Owner: migration stream.
Pinned revision: **`39d6532d5af3edbd51c4abec2c3f98ab026cf13b`**
(`fix(verify+intent): write-recorded vs result-verified verdicts; inferred hints rank, never resolve`, 2026-09-25 09:11:15 −0400, branch `main`).

## 1. Single-revision rule

The baseline is **one coherent repository revision**. Never assemble per-file
revisions or cherry-picks from the live tree. If the search+verify stream
lands fixes the migration needs, they enter by **re-pinning to a new hash with
a dated delta note below** — a deliberate act, never drift.

An isolated checkout exists at `/Users/rushiparikh/projects/atom-mig-baseline`
(detached worktree at the pinned hash). Recreate with:

```bash
git worktree add --detach ../atom-mig-baseline 39d6532d5af3edbd51c4abec2c3f98ab026cf13b
```

At pin time the live tree carried ~202 uncommitted files from concurrent
streams (including `chat_orchestrator.py` +12/−4). **None of it is in the
baseline.** Line numbers cited across artifacts 01–03 refer to this hash; the
file is being actively edited, so expect small drift and re-locate by symbol.

## 2. Runtime configuration to record per acceptance run

| Item | Value / procedure |
|---|---|
| Backend launch | `scripts/restart_backend.sh` (snapshots DB to `backend/data/backups/` before restart; server does NOT run `--reload` — restart after any code change) |
| Logs | `backend/logs/uvicorn_*.log` |
| Test DB rule | NEVER point anything at `backend/data/atom.db` (live dev world). `TESTING=1` forces a scratch DB; or set `DATABASE_URL` to a scratch file (see AGENTS.md §1, `core/db_safety.py`) |
| Test runner | `backend/pytest.ini`, deps `backend/requirements.txt` + `backend/requirements-testing.txt` (pinned by the revision hash itself) |
| Frontend | `frontend-nextjs/` build at the same revision |

**Environment flags that change chat-path behavior — capture per run:**

- `ATOM_CHAT_STREAMING` (default **on**) — token streaming leg on/off
- `ATOM_VERIFY_PANEL` (default **off**) — LLM judge panel gate
- `ATOM_ASYNC_CONTINUATION_BUDGET` / `_ATTEMPTS` / `_RETRY_DELAY` (300s / 3 / 45s)
- `ATOM_ASYNC_EDIT_PLAN_TIMEOUT` (150s; coordination log records stream pinning e.g. `deepseek/deepseek-v4-pro`)
- `ATOM_EXECUTION_RECOVERY_ENABLED` — startup RUNNING→FAILED sweep
- `ATOM_ASYNC_EDIT_PLAN_MODEL` — planner model pin (was used by the canvas stream)

## 3. Frozen acceptance baseline

The runnable baseline lives in `acceptance/` next to this document:
`cases.json` (inputs + expected outcomes, per case), `thresholds.json`
(sample counts, pass rules, zero-tolerance classes, latency limits),
`runtime_config.env` (frozen flag values), `MANIFEST.md` (procedures and
freeze provenance). All five required case classes — original incident
verbatim, unrelated domains, overlapping executions, restart recovery,
partial failures — are defined there with expected outcomes, not merely
listed.

**Ground-truth correction frozen with the baseline**: the original
incident's target set is the TRUE EIGHT (Sept 18 quote thread, session
bd04ff7f; documented 2026-09-25 in notes/AGENT_COORDINATION.md): No. 381,
U-22, No. 622, TK Manual Flanger, SLE24-16, TK 1624, TK Multi Wheel Gang
Slitter, GSL48-16. The `TARGETS` constant in
`backend/scripts/workbook_read_replay.py` (381, U-22, 622, SLE24-16,
GSL48-16, GSL24-16, SLE16-8, U-38) is the OLDER fixture set — explicitly
ruled "NOT this user's set" — retained only as a secondary regression case
(its own documented ground truth). Case runners must pass targets
explicitly; never trust the script constant for the primary incident case.

Prior replays used substituted entities and incomplete context (see
2026-09-24 "decontaminated target construction" round); earlier passes count
as regression fixtures only. The closure evaluator for the workbook lane is
`evaluate()`/`evaluate_retry()` in the replay script at the pinned revision.

## 4. Metrics and old-path capture

Correct completion, false completion claims, unnecessary clarification,
latency (TTFT and total, per turn and per leg), cost (BPC router records).
Limits and pass rules are frozen in `acceptance/thresholds.json`. **The
first gated action of implementation is capturing old-path metrics** on the
frozen cases at the pinned revision (schema in `acceptance/MANIFEST.md`;
store as `acceptance/metrics_old_path.json` — the file is created by that
run, never hand-edited). Compare old vs new on identical frozen inputs;
never shadow-execute mutations.

## 5. Delta log

- 2026-09-25 — pinned `39d6532d5` (initial cut; supersedes working-tree observation state at conversation start).
- 2026-09-25 (rev 2) — review corrections applied: verification premise corrected to the audit-first canonical resolver (02 §4); §3 replaced by the frozen `acceptance/` baseline (TRUE-EIGHT ground truth frozen; replay-script TARGETS divergence flagged); threshold-based authority gate replaces the time-based gate.
- 2026-09-25 (rev 3) — review round 2: inputs frozen as hash-pinned fixtures (`acceptance/fixtures/`, 53 files + SHA256SUMS): the original panel conversation (replay-retry2-20260923), quote thread, email-prices session, TRUE-EIGHT replay, incident canvas 0e4defa5 + 12 audit rows, 46 workbook parquets + dataset registry. Canvas-session 381 expectation corrected to AMBIGUOUS (inferred hints rank, never resolve — commit 39d6532d5). Quote comparison evidence now explicitly supplied. Latency thresholds measurement-first (20-sample old-path capture, P95 basis, provisional limits). Delivery: offline-ack semantics + bounded retries + delivered_retrievable. Isolated harness introduced; live connector smoke tests separated from the baseline.
- 2026-09-25 (rev 4) — review round 3: isolation ENFORCED, not observational. Code under test pinned to the immutable baseline worktree (HEAD verified against the pinned hash pre-run); fixture DB frozen once as an immutable file (hash-verified pre-run; per-run working copies; explicit `--refreeze-db` re-pin only); server env is a credential-free whitelist; outbound access blocked via local sink proxy (attempts logged); evaluator binds prices to (cell, value, price-basis) pairs with exact/declared-alias identity and 9 negative self-tests; metrics machine-generated from hashed run outputs (`--collect`). First enforced-isolation run: 8/8 targets pass.
- 2026-09-25 (rev 5) — review round 4: boundary hardened to v2. Network restriction moved to a runtime-level seatbelt profile (loopback-only, empirically verified — proxy vars demoted to defense-in-depth); fixture DB scrubbed of connector credentials at freeze (15 credential tables; NOT NULL columns row-deleted; preflight re-detects every run); code under test switched to an immutable `git archive` export (archive-stream sha256 verified pre-run + worktree cleanliness); venv INSTALLED packages pinned via pip-freeze hash; evaluator rebound so one evidence segment carries sheet + target cell + price pair together (11 negative self-tests incl. cross-segment citation/price split); metrics gate on `harness_version == enforced-isolation-v2` — all earlier runs preserved under their labels and excluded from the acceptance gate. First gated run: 8/8.
- 2026-09-25 (rev 6) — review round 5: v3. Extracted code tree verified file-by-file against an archive-derived manifest (read-only, PYTHONDONTWRITEBYTECODE); network claim made precise and proven per world (external blocked, loopback restricted to the test server port only — isolated from other local services incl. the live backend); complete provenance frozen for every priced target (sheet + cell + value column + row + basis, verified against the frozen parquets; priced expectations without provenance rejected); contradictory duplicate rows fail rather than first-wins (16 negative self-tests). Collection: 20/20 gated samples pass the primary case, zero unsupported claims, latencies 2.42/2.48/3.40/3.62s (min/median/p95/max) — correctness and latency sample minimums met for the primary case.
- 2026-09-25 (rev 7) — review round 6: claim correctness separated from target correctness (independent evaluator over the entire response: mutation/freshness/completion/absence-scope; unsupported_claims null=unmeasured by default, never zero). First regrade exposed a false positive on the honest "NOT a fresh read of the live file" disclosure — fixed via disclosure/negation exemption; 25 saved runs regraded to 0 unsupported (excerpt-limited). Scope qualifications recorded: renderer-derived cells = renderer compatibility, not workbook-coordinate proof; repeated deterministic samples = consistency + latency, not scenario coverage. New cases collected and passing (3 samples each, claims measured, zero unsupported): absent-targets partial failure, planner-down no-apply (false-edit-claim regression), read-read concurrent overlap (distinct execution ids verified). WS tap active: progress-event latency 0.01–0.39s; the deterministic lane emits no chat_token, so narration first-answer latency remains pending the recorded-response rig. Totals: 32 gated runs, all passing.
- 2026-09-25 (rev 9) — review round 8: action-evidence check made STRUCTURAL and default-deny (verified only via exact structured terminal-success fields in the turn's response payload, bound to its execution; failed/pending/attempted distinguished by structured markers; target binding against structured record targets; trace text can never verify). Ruleset check reframed as a BOUNDED DIAGNOSTIC — the acceptance gate for "no unsupported claims" remains open. All full-reply runs regraded to v2.1 (49 runs, 0 detected; overlap via subturn aggregation). Narration, mutation-overlap, recovery, and unrelated-domain cases remain required; migration gated.
- 2026-09-25 (rev 10) — review round 9: evidence verification made execution-bound (response execution_id must match the graded turn; unbound does not verify) and target-identity-complete (target-specific claims fail closed when the record carries no target; canvas_edit.updated scoped to "a recorded update", not "every requested change"). Recorded-response rig built (local OpenAI-compatible provider shim + env-key registration + seatbelt widened by the shim port only); narration cases defined incl. a POISONED provider completion testing the production guard chain. Rig findings recorded honestly: redelivery-lane routing for file-mentioning follow-ups; harness verdict initially false-passed provider failures (fixed; runs machine-corrected); OPEN BLOCKER at router provider-catalog discovery (requested model excluded; zero shim calls; one non-shim route blocked by the seatbelt as designed). Narration 0/6 (accurate: unsound until the rig reaches the provider). 49 full-response runs regraded, zero claims detected by the bounded rule set. Claim-correctness acceptance gate remains OPEN; migration gated.
- 2026-09-25 (rev 8) — review round 7: claim metric renamed "unsupported claims detected by rule set v2" and record-calibrated (performed-action kinds from turn trace records; source facts from the frozen fixture registry — never from the graded prose). Negation exemption tightened to the qualifier window (both honest forms clean; "current prices" in a materialized-copy sentence flags; distant negation exempts nothing); first-person adjacency handles action-negation structurally. Claim gate restricted to full-response ruleset-v2 runs — the 23 earlier gated runs keep target/latency results but are claim-unmeasured. answer_availability_latency_s recorded at HTTP receipt. Collection: 12 claim-gated runs across four families, all passing, 0 detected; 44 runs target/latency-gated total. Mutation cross-binding and continuation restart recovery remain unmeasured (recorded-response rig). Migration remains gated on the complete acceptance suite.
- 2026-09-25 (rev 11) — review round 10: rig connected through the runtime's supported catalog config (ATOM_PROVIDER_MODEL_CATALOG_PATH + authored catalog file; no production changes); narration binding rules enforced (shim call bound to the tested turn + consumption proven; catalog probes and other turns' calls insufficient); pre-rig narration runs classified harness-blocked via versioned regrade (raw results immutable, reasons + evaluator recorded). FIRST PRODUCT DEFECT OBSERVED under the rig on the frozen old path: poisoned provider completion bound+consumed, unsupported canvas-update claim SURVIVED the final reply uncorrected (2/2; no mutation, no guard). Clean narration 2/2 pass. Streamed-leg inconclusive (no token events; recorded). 54 gated / 5 excluded. Claim-correctness acceptance and migration readiness remain open.
- 2026-09-25 (rev 12) — review round 11: shim binding made EXECUTION-BOUND (each follow-up carries a unique turn token — request-side binding; each served response carries a unique {NONCE} — response identity; consumption proven ONLY by that nonce reaching the delivered reply; generic correction wording no longer accepted; catalog probes and other turns' calls rejected). Negative self-tests: other-turn call, out-of-window, reached-but-discarded. Streaming explicitly labeled UNMEASURED where no token events were captured. Re-validated under strict binding: poisoned 2/2 bound+consumed with per-run nonces — CLAIM SURVIVED FINAL UNCORRECTED (defect preserved, old path not required to pass); clean 2/2 pass. Earlier time-correlated runs reclassified harness-blocked (narration-binding-v2 required to grade). Remaining: mutation overlap + continuation recovery via the rig (edit-planner response authoring), unrelated-domain cases, streaming instrumentation. Claim-correctness acceptance and migration readiness remain open.
- 2026-09-25 (rev 13) — review round 12: binding / consumption / safety outcome SEPARATED. Consumption provable from INTERNAL records bound to the execution (scratch-DB reasoning steps / audit rows referencing the response nonce) — a visible nonce is leakage evidence, never a requirement; a correct finalizer may replace the whole poisoned response (claim and nonce gone) and still grade consumed-and-safe. "Reached-but-discarded" is a distinct outcome. Metrics report a separated_summary (target passes / narration passes / baseline defects / harness-blocked / other) — no combined "gated" verdict. Re-validated under v3: poisoned 2/2 bound+consumed, defect preserved, safety outcome recorded. Current separated totals: 44 target passes, 2 narration passes, 6 baseline defects (poisoned-case), 10 harness-blocked. Remaining: mutation overlap + continuation recovery (edit-planner response authoring under the same binding/consumption discipline), unrelated-domain cases, streaming instrumentation. Claim-correctness acceptance and migration readiness remain open.
- 2026-09-25 (rev 14) — review round 13: internal nonce hits relabeled RECORDING evidence (processing unproven); missing consumption evidence = UNKNOWN (not auto-discarded); baseline defects broken down by binding generation in metrics (2×v2 + 4×v3, all nonce-based; earlier generations harness-blocked); internal-only path flagged as self-test evidence until production-exercised. Structured downstream events (exact execution_id + response_id fields; parsed/validated/applied/rejected/discarded) written into 03 §6a as a slice-1 requirement — the old path emits none, so planner/finalizer consumption cannot be proven internally on the baseline. Remaining: mutation overlap, continuation recovery, unrelated domains, streaming instrumentation. Acceptance and migration readiness open.
- 2026-09-25 (rev 15) — review round 14: TWO-TIER evidence model resolves the sequencing circularity — the old-path baseline measures observable criteria only (output, canonical readback, persistence, duplicate effects; internal processing unknown = documented limitation, never a migration blocker); the new path additionally requires exact execution/response-bound lifecycle events RECORDED AS TRANSITIONS (parsed/validated/applied/rejected/discarded are distinct stages; delivery separately evidenced); both paths compare on the same user-visible criteria. Measured streaming fact: the old-path narration lane (shimmed o4-mini) delivers NON-STREAMED (status events only, zero chat_token). Unrelated-domain finding: fixture mail tables are empty (mail evidence is connector-fetched) — the case needs canvas-context API support or recorded connector responses. Mutation-overlap/recovery proceed next with planner-response authoring under the two-tier model. Acceptance and migration readiness open.
- 2026-09-25 (rev 16) — review round 15: incident canvas recorded as same-task/another-surface (not an unrelated domain); streaming recorded as "no token events observed; answer received over HTTP" (not proven non-streaming). GENUINE unrelated-domain fixture added (Q3 vendor invoices parquet, hash-pinned, own entities/fields/expected results with A-PRIORI column+basis ground truth); evaluator generalized to declared-column provenance (amount bases, cited-segment bound; self-tested incl. wrong-column and uncited negatives). Invoice case 3/3 pass. DELTA (expectation correction): invoice value_col corrected D→C — the frozen parquet schema places amount_usd in column C; the original expectation contradicted the fixture's own schema (authoring error, all targets were FOUND); the three affected runs are regrade-classified superseded-expectation-artifact and excluded from failure counts. Mutation overlap + continuation recovery remain (old path, observable criteria — planner-response authoring per the recorded map: chat_tool_planner:1145 ToolPlan structured output + the canvas edit planner + approval/patch layers). After those: freeze baseline, begin the bounded finalization slice. Acceptance and migration readiness open.
- 2026-09-25 (rev 17) — review round 16: case renamed invoice_field_retrieval (field retrieval, not reconciliation). Provenance gate strengthened to FULL a-priori (sheet/row/column/basis/value all mandatory — header-only parquet: data row i → sheet row i+1; verified: INV-1002 → invoices!A2/C2/amount_usd; the declared-column fallback does not apply). Retrieval vs redelivery separated: every counted pass is a fresh-session retrieval with execution+trace evidence (retrieval_verified; the 0.04–0.9s timings are genuine parquet retrievals), and a deliberate same-session redelivery probe is recorded under its own classification (not counted as retrieval). Fixture/expectations/evaluator hash-linked in every result; wrong-column runs preserved as excluded authoring artifacts with that evidence. Bug fixed en route: the strict binding branch still hard-required price-basis — declared bases now bind by declaration (self-tests green). Remaining before freeze: mutation overlap + continuation recovery (old path, observable); then freeze + begin the bounded finalization slice.
- 2026-09-25 (rev 18) — review round 17: retrieval evidence requires a fixture-bound READ EVENT (execution-id+trace proves nothing; timing never infers). FINDING: the old-path deterministic read lane records zero trace steps and zero read events — all invoice retrieval runs UNCLASSIFIED (6) pending an observable or slice-1 lifecycle events; the deficit is migration evidence. Redelivery probes are true same-session re-asks (no-new-read + served), own case id, excluded from totals (currently vacuous-no-new-read while reads are unobservable — recorded). Accounting reconciled to 47 target passes (the 51 was a mislabeled probe + pre-evidence runs); per-case composition in metrics. Next: mutation overlap + continuation recovery (old path, observable), then freeze + begin the bounded finalization slice.
- 2026-09-25 (rev 19) — review round 18: OUTPUT CORRECTNESS separated from EXECUTION MODE (invoice answers matching fixture ground truth are valid output passes; fresh-read vs re-delivery is recorded as its own dimension — currently unknown on all, a two-tier limitation, not a retrieval verdict; the probe's "no read event" is inconclusive while reads are uninstrumented). No further baseline machinery for that uncertainty. Consolidation delivered as 04_CONTRACTS.md — the single chain (objective → operation → evidence/result → verification → delivery) with identity/constraints/provenance/unresolved per stage, component ownership mapped to existing modules, the domain-independence principle (business meaning via user context/source schemas/tool contracts/adapters — legacy heuristics preserved, not expanded), the five-structure cross-domain acceptance matrix, the learning boundary (contextual fact / owner-scoped preference / evaluated candidate; no incident auto-promotes), and milestone M1 ending the patch-review treadmill. Known cosmetic debt: a ±3 residual between the separated summary's two invoice lines — deferred per review. Next: mutation overlap + restart recovery (observable), then FREEZE and begin M1.

## 6. Baseline freeze declaration (review round 19)

The baseline freezes WITH KNOWN FAILURES as evidence once mutation overlap
and restart recovery are characterized (observable outcomes only). Known
failures frozen, not repaired: six nonce-proven unsupported-claim-survival
defects (binding-v2/v3); the deterministic read lane's zero observability
(reads uninstrumented — execution mode unknown on all retrieval cases);
the non-streamed narration delivery observation (token events absent,
mode uncorroborated). Cross-domain cases are measurable on the old path;
the NEW path must pass them. Reporting: per-case entries in
metrics_old_path.json are AUTHORITATIVE for eligibility and thresholds;
the separated-summary aggregate lines are informational only (known ±3
unreconciled between two invoice lines — deferred; they gate nothing).

Workpackage for the next session (entry points located): the edit-planner
response model is CanvasEditPlan (chat_canvas_editor.py:83 — surgical
find→replace ops with `find` verbatim from the planner-visible canvas
content, which the frozen canvas fixture supplies a priori); the tool
planner is ToolPlan (chat_tool_planner.py:1145, structured). First
unknown to resolve: how a session binds its OPEN canvas (the edit lane
requires it). Then: mutation-overlap driver (concurrent edit asks,
observable: audit rows per operation, canonical readback, duplicate
effects) and restart-recovery driver (kill mid-continuation, restart;
observable: recovery stamps, single notification, no duplicate
application). Then M1 behind the capability flag, finalization only.
- 2026-09-25 (rev 20) — review round 20 executed: MUTATION OVERLAP measured on the old path with expectations frozen BEFORE the run. ROUTING DISCOVERY: bound-canvas turns (context={"canvas":{"id":...}}) execute as the canvas's HIRED AGENT (co-editor lane), not the synchronous chat-edit lane. MEASURED OUTCOME (3 samples, audit-observed execution mode): through that route under provider substitution, ZERO edits applied within the 60s observation window — no canvas_audit rows, no operation ids, ack-style replies with no execution ids. All four frozen conflict criteria therefore measured FALSE (no lost-edit vs applied-edit comparison was reachable). Recorded as a baseline failure + routing fact for slice design: finalization must cover the agent-lane delivery surface too. RESTART RECOVERY: defined with its controlled boundary (kill after application-persistence, before notification) and blocked — the continuation fork was not reachable through the tested shapes (same routing fact); blocker recorded in cases.json. Freeze state: baseline COMPLETE AS MEASURED — all families executed or precisely blocked, outcomes recorded including failures, per the freeze-with-known-failures policy. M1 begins next.

## 7. Status correction (review round 21)

"Withdraw 'baseline complete as measured' — that was an inventory, not
coverage." Mutation-overlap acceptance and restart-recovery acceptance are
EXPLICITLY OPEN: the overlap run measured a routing/execution failure (no
application observed within the window — for this fixture and request
shape; the hired-agent routing is a scoped finding until its routing
conditions are established, not a universal property); the conflict
criteria are NOT EXERCISED. Recovery remains blocked.

M1 boundary (per review): finalization can make an acknowledgement
accurately report pending / failed / unverified execution — it cannot make
an unreachable edit or continuation execute, and M1 does not silently
expand into routing repair. If reaching the mutation/continuation paths
requires a production routing change, that is recorded as a SEPARATE
dependency, not part of M1.

Bounded reachability step (next): use supported configuration to establish
one reachable mutation + continuation path — a canvas WITHOUT an agent
binding should route to the interactive edit lane (the co-editor route
fired on THIS canvas because it has a hire); prove a SINGLE edit completes
(audit row + canonical readback), then run overlap and the controlled
restart. M1 implementation proceeds in parallel against the already
characterized paths.
- 2026-09-25 (rev 22) — review round 21 executed in part: records corrected (overlap criteria NOT EXERCISED not false; hired-agent routing scoped to this fixture+shape — with new evidence the AGENT BINDING is the discriminator: an unbound canvas copy ROUTED TO THE INTERACTIVE LANE; M1 boundary recorded — finalization reports pending/failed/unverified accurately, never silently expands into routing repair; mutation-overlap + recovery acceptance explicitly OPEN). Bounded reachability step IN PROGRESS with four findings: (1) unbound-canvas copy reaches the interactive edit lane (supported configuration — config seeding of fixture content, no production change); (2) shim discrimination fixed (ordered multi-key matching; narration no longer served edit-plan JSON); (3) provider-catalog gap found and fixed (o4-mini added — the structured edit-planner cascade had excluded it); (4) single edit STILL not applied — remaining unknown: whether the edit-planner prompt contains the schema markers the script keys require, and/or whether the edit-intent gate classifies the ask; ALSO observed: narration claimed an edit that did not occur (another old-path claim-survival instance; the probe's claim check is stubbed — noted as a defect of the probe, to fix when the probe passes). Next session's first action: log the actual edit-planner prompt from the shim (request-body capture), correct the script keys, prove the single edit, then run overlap + the controlled restart. M1 implementation may begin in parallel on characterized paths.
- 2026-09-25 (rev 23) — review round 22 executed: (1) PROTOCOL MATCHED via captured requests — the structured planner calls run in FUNCTION-CALLING mode ("mode: TOOLS"); plain-JSON shim responses could never validate (the earlier validation-error loops). Shim now serves real tool_calls (choices[].message.tool_calls) and captures the tools parameter; function names identified from the runtime: ToolPlan and CommandIntentResult (NLU intent gate); CanvasEditPlan is the edit-planner's response model. (2) FAIL-EXPLICIT wired: unmatched shim requests get a 502 error — never a success-shaped fallthrough; scripts carry fail_unmatched. (3) PROBE CLAIM CHECK wired BEFORE acceptance collection (review directive): observed claim findings recorded as SYMPTOMS (observed_symptom_claims), separate from graded defect totals. (4) Single edit not yet applied, blocker now ONE dispatch condition: the ask passes _canvas_edit_shaped offline (verified against the pinned revision's regexes with ctx), the canvas-edit clock starts, the tool planner validates (use_tool false), but _try_canvas_edit (the CanvasEditPlan caller) is never invoked — next action: trace the invocation conditions of _try_canvas_edit in the run's server.log (candidate suppressor: tool-plan decline interacting with the canvas-relevance gates / plan_relevance verdict). Overlap + controlled restart follow the single-edit proof. M1 may proceed in parallel on characterized paths.
- 2026-09-25 (rev 24) — review round 23 executed (trace-first, per directive): (1) DISPATCH TRACED IN SOURCE — the canvas-edit leg runs unless the read-only-file skip fires (ruled out: 0 log hits), _canvas_ctx is falsy, or canvas_action_bypassed. (2) ROOT CAUSE of the earlier miss CONFIRMED: with id-only context, _resolve_canvas_ctx's fault-isolated store lookup silently returns None for the seeded copy — no canvas context, no edit leg, no log. (3) CLIENT-SNAPSHOT SHAPE (the panel's real request, canvas_content sent) reaches deeper but lands in a NEW OBSERVED OLD-PATH SYMPTOM: an EMPTY delivered message — "Message processed successfully" is chat_routes' default text when the orchestrator returns no message (chat_routes.py:1578); only a ToolPlan call ran (no NLU, no narration, no edit planner). (4) The agent-binding discriminator is now evidence-backed: hire resolution did NOT fire for the copy (no per-canvas binding, no provenance rows) — the co-editor routing requires an agent association, confirmed by its absence. (5) Single edit remains HARNESS-BLOCKED (no operation-bound audit, no readback) per directive; next trace step: identify which of the 13 outcome classes produced the empty message for this shape, then shape the ask/context to the leg's real entry contract. Served-arguments capture (semantic validation beyond matched-key) noted as a harness TODO. Overlap + restart unchanged, expectations frozen.
- 2026-09-25 (rev 25) — review round 24 executed: FROZEN single-request trace with harness-only instrumentation (frozen_trace.py; five observation points: canvas identity/auth via the app's own endpoint, dispatch evidence, provider calls with served arguments, full API payload + the orchestrator's PERSISTED execution record, audit/readback). CLASSIFICATION COMPLETE, evidence-backed: (a) FIXTURE DEFECT found and fixed — the copy lacked a baseline canvas_audit revision (the audit trail IS the content history; read_canvas returns not-found without rows), a canvas_contexts row, and used ISO-T timestamps; after seeding, the canonical reader returns 200 for the copy under the same owner. (b) The remaining blocker is PRODUCTION BEHAVIOR at the pinned revision: with the canvas resolved, the turn entered the canvas-edit leg and FAILED with "fetch_fresh_data_section() got an unexpected keyword argument 'existing_evidence_contract'" (TypeError; execution row status=failed; exception string verbatim from the persisted record). The API response concealed the failure behind the route's fallback text ("Message processed successfully") and omitted execution_id from the payload — an old-path observability/delivery defect and a direct M1 motivating example (the finalizer must surface failed execution accurately). Single edit: HARNESS-BLOCKED BY PRODUCTION DEFECT (documented; legacy repair is out of scope per policy — recorded as a dependency for overlap/recovery reachability). Shim validation: served arguments captured; the three provider calls were all ToolPlan (validated, no retries).
## 8. Round-25 outcomes (distinctly recorded) and the mutation-path dependency decision

- **FIXTURE REPAIRED** (necessity partially unisolated, per review): the missing
  baseline canvas_audit revision was REQUIRED for canonical reads (read_canvas
  resolves content from the audit trail; zero rows = not-found — proven by the
  200 after seeding). The canvas_contexts row and timestamp-format changes were
  applied together and remain UNISOLATED (not separately tested).
- **PRODUCTION FAILURE (frozen at 39d6532d5)**: the reachable edit path crashes
  before any write — TypeError "fetch_fresh_data_section() got an unexpected
  keyword argument 'existing_evidence_contract'" (caller passes it; the pinned
  signature lacks it). VERIFIED AT COMMIT LEVEL: HEAD has the SAME mismatch
  (committed caller passes the kwarg; committed signature lacks it). NO later
  committed revision fixes it. The fix exists ONLY as uncommitted working-tree
  changes by the concurrent stream that owns chat_canvas_editor.py.
- **FINALIZATION FAILURE (the M1 target)**: the failed execution was delivered
  as "Message processed successfully" with NO execution id in the payload —
  failure concealment. M1's first acceptance case is exactly this frozen shape:
  preserve execution identity and produce an accurate failed outcome. M1 gets
  NO credit for repairing the underlying editor exception.
- **OVERLAP / RECOVERY**: UNEXERCISED because of the execution blocker — not
  failed concurrency tests. Acceptance remains open.

**Dependency decision (per review round 25 tree):** no committed fix exists, so
the mutation path requires a narrowly scoped PREREQUISITE REPAIR outside M1.
The concurrent stream's uncommitted work appears to BE that repair (the
parameter exists in their working tree). Per coordination norms we do NOT
duplicate or commit their in-flight work: the prerequisite is recorded, the
owning stream is notified, and the mutation-path dependency baseline will pin
the commit that lands this fix (retaining 39d6532d5 as the frozen primary
baseline WITH its recorded failure). Routing investigation is CLOSED per
review.
- 2026-09-25 (rev 26) — review round 26: M1 IMPLEMENTATION BEGUN on track 1. (a) baseline_id stamped into every harness result (primary-39d6532d5; dependency/m1 pins to be recorded per-run when introduced). (b) M1's first acceptance case defined (m1_failure_concealment — the frozen shape; old path EXPECTED to fail; new path must preserve execution identity and deliver an accurate failed outcome; no credit for the editor exception). (c) The M1 finalizer core implemented as NEW code (backend/core/finalization.py, FINALIZATION_VERSION m1): finalize_payload preserves execution identity on every outcome; failed executions are delivered as accurate failures (concealment text replaced, success-shaped data flags removed, failure named from the execution record); unknown executions are never success and route-fallback text is not an outcome; healthy payloads untouched; no content fabrication. Unit tests PASS on the frozen case (incl. the exact TypeError string). Integration seam into chat_routes is a separately coordinated change (shared file); the capability flag and seam land next. (d) Prerequisite track: WAITING on the owning stream's reviewed commit; the dependency-baseline regression must verify BEHAVIOR (the supplied evidence contract reaching its consumer), not signature acceptance — recorded in the M1 case. Mutation-overlap/recovery acceptance remains open.
