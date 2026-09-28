# Ollaya Decision Plane — Integration Plan for Atom

> **Goal:** cut LLM classification cost/latency and lift long-thread accuracy + task completion by adding a local, calibrated decision sidecar (choice/score/noul) in shadow-first, Atom-style.
> **Non-goals:** replace reasoning, memory retrieval, oracle verification, embeddings, vision.
> **Repo:** `projects/atom`. Conventions: `AGENTS.md` (whole-repo context, evidence, TDD red-green-refactor, trail in `notes/AGENT_COORDINATION.md`), `CLAUDE.md` governance/shadow/certify patterns.

## Why (Atom-specific)

| Today (LLM-paid, uncalibrated) | Ollaya replacement |
|---|---|
| `backend/core/intent_classifier.py:64` CHAT/WORKFLOW/TASK via LLM JSON | `choice` + `confidence`, shadow-logged vs LLM |
| `backend/core/turn_fact_extractor.py:19` `model="fast"`, 2s timeout, regex skips ~40% | `noul: has_durable_fact?` pre-filter + `choice` category hint; LLM stays extractor |
| `backend/core/llm/stage_router.py:1` heuristic `spinning/exploring` signals | add calibrated `on_task, stuck, needs_escalation` scores as corroborating signals |
| `backend/core/agent_objective.py` `definition_of_done` checked by reasoning | `noul: task_done?` fast pre-check before expensive check |
| `backend/core/sandbox_gate.py`, `mcp_service.call_tool` P2/P9 gates, HITL | `agent`-style `run/ask/block + risk` pre-gate (advisory until certified) |
| `backend/tools/canvas_tool.py`, `core/canvas_logic_service.py`, `integrations/universal_integration_service.py` branch/pick via LLM | `choice` for canvas edge + integration pick |

Memory (`CONTEXT_MEMORY.md`, GraphRAG, hybrid search, `TurnFact` SQL truth) and oracle (`core/oracle/`) stay authoritative. Ollaya is a feature/signal, never source of truth.

## Architecture

```
Agent turn → DecisionService.decide() ─┬─► Ollaya :11435 (/v1/systemone, Modelfile question sets)
                                       └─► fallback: existing LLM path (on timeout/error/flag-off)
Audit: ollaya_decision_audit (would-have vs applied, Brier/ECE inputs)
Flags: runtime_settings (env wins > DB row > default), never raises, circuit breaker
```

New module: `backend/core/decision_service.py` (+ `backend/core/decision_questions.py` Modelfile-derived question sets, `backend/tests/test_decision_service.py`).
Settings catalog additions: `ATOM_OLLAYA_ENABLED` (default false), `ATOM_OLLAYA_URL`, `ATOM_OLLAYA_MODEL` (default `laya`), `ATOM_OLLAYA_TIMEOUT_MS` (default 800), `ATOM_OLLAYA_FORCE_ENFORCE` (default false), per-surface `..._SPLIT` harness weights.
Ops: Personal Edition sidecar in `docker-compose-personal.yml` (`ollaya serve`, CPU, default `~/.ollaya/models` on internal SSD); `ATOM_LOCAL_ONLY=true` routes here; no PHI leaves host (weights pinned sha256 upstream).

> **Storage decision (2026-09-25, measured):** portable drive REJECTED. Cold load `laya` internal SSD 4.6s vs Seagate Portable Drive 16.1s (3.5x, +11.5s); warm inference identical ~0.22s. Cold penalty breaks the 2s extraction budget and agent-loop usability → keep `OLLAYA_MODELS` default (internal). External copy removed.

## Phases (each: failing test first, shadow → calibrate → consent-gated enforce)

### Phase 0 — Spike + baseline (0.5–1 day)
- Stand up `ollaya serve` locally, pull `laya`; record p50/p95 CPU latency on 5-question batch.
- Baseline from existing audit tables: intent misroutes, `turn_fact_extraction_failure` rate, extraction cost/latency, stage-router RESCUE/LOSS quadrants.
- Exit: numbers in commit message; go/no-go on latency (<800ms CPU acceptable for cron/agent loop, not inline voice).

### Phase 1 — DecisionService abstraction (1–2 days)
- `decision_service.py`: `decide(state, questions|preset, model)` → `{answers, confidences, latency, source}`; timeout→fallback; failure→`[]`/no-op; Prometheus-style counters (`ollaya_fallback_total{reason}`); TTL anti-thrash cache.
- Runtime-settings wiring + settings-catalog entries; `scripts/restart_backend.sh` verified (no `--reload`).
- Tests: timeout, malformed payload, flag-off, cache, never-raises (mirror `turn_fact_extractor` contract).
- Exit: unit suite green; no caller wired yet.

### Phase 2 — Intent routing shadow (2–3 days)
- Wire shadow into `IntentClassifier` + `AtomMetaAgent.execute()`: log `ollaya_choice` vs LLM `category/confidence` to `ollaya_decision_audit`; responses still from incumbent.
- `scripts/calibrate_decision_router.py`: accuracy, Brier/ECE, threshold sweep for `choice>=0.6` act rule; per-`agent_id` readiness (follow `stage_router` `resolve_agent_policy` pattern).
- Exit: certify thresholds; enforcement stays OFF.

### Phase 3 — Turn-level judgments for long threads (3–4 days)
- Fire-and-forget hook next to `extract_from_turn`/`on_pre_compress`: `has_durable_fact, on_task, task_done, pending_question, stuck` (`noul`/`score`).
- Consumers (all advisory, none may skip verification): when `has_durable_fact<=0.2`
  propose skipping the LLM extraction ONLY after the facts-join measures
  missed-fact precision ≥0.95 at real volume (see learning 10); `stuck`/`on_task`
  as corroborating stage-router signals; `task_done>=0.8` ORDERS the
  `definition_of_done` verification sooner (oracle still decides — a probability
  is never evidence an operation succeeded, and must never suppress the check);
  inject `pendingQuestions` into prompt assembly alongside Tier-1 SQL facts.
- Tests: 5-category taxonomy parity (`turn_fact_categories.py`), EWMA/supersede untouched, queue worker never blocks response.
- Exit: fewer wasted extractions, stuck-escalations audited, no prompt regression.

### Phase 4 — Governance / canvas / integration gates (3–4 days, each independently flaggable)
- Sandbox/capability path: advisory `run/ask/block + risk` at `sandbox_gate.evaluate_tool_call`; partial/ambiguous → existing `ProposalService` (mirror `MATCH_CONFIDENCE.md` tri-state).
- Canvas: one `choice` branch node via `CanvasLogic` sandbox runtime (e.g. support-triage or scheduler branch).
- Integrations: `choice` integration-picker hint in `UniversalIntegrationService` + `noul: needs_approval/contains_PII` before Outbound Gatekeeper.
- Exit: all paths default advisory; HITL/proposal semantics unchanged.

### Phase 5 — Consent-gated enforcement + graduation (1–2 days)
- Automation pass `off|notify|approve|auto` (default `approve`), always-automatic revocation on regression — copy `trust_calibration/automation.py` + `stage_router_automation.py` ledger pattern (`*_automation_actions`, monotonic PK, `/health/decision-router`).
- Certify gate (suggested): Brier ≤0.25, denial-coverage ≥0.7, n≥30 per surface (same as trust gateway); per-workload `enforce` + `confidence_threshold` overrides.
- Docs: `docs/architecture/DECISION_PLANE.md` (final), `docs/guides/RUNTIME_SETTINGS_GUIDE.md` entries, coordination-doc trail.
- Exit: at least one surface (intent shadow) certified; others remain shadow until their numbers pass.

## Status (2026-09-25, live-verified)

- [x] Phase 0: ollaya 0.6.0 installed (`~/.local/bin`), `laya` pulled. Cold 4.6s / warm 0.22s internal SSD.
- [x] Phase 1: `backend/core/decision_service.py` (8 tests) + `ATOM_OLLAYA_*` catalog flags. Live: preset/HTTP/dict-state/fallback/breaker all green.
- [x] Phase 2: intent shadow live. `decision_questions.py` (CHAT/WORKFLOW/TASK choice), `decision_shadow.py` (fire-and-forget, hash-only PHI), `DecisionRouterAudit` (self-provisioned, trust-calibration precedent), `scripts/calibrate_decision_router.py` (Brier/ECE/sweep, exit-code verdict). Live: 3 shadow rows, warm shadows ~90ms, calibrator HOLD (n=3 < 30) as expected.
- [x] Phase 3: turn judgments live (record-only). `TURN_JUDGMENTS` (5 noul), `DecisionTurnAudit`, wired fire-and-forget at all 3 extraction hooks (`generic_agent` digest, meta session-end + per-step), `scripts/calibrate_turn_judgments.py`. Live: fact-rich→fact 0.86/done 0.90, stuck-loop→stuck 0.81, completed→done 0.58 — all sane; calibrator HOLD (no outcome join yet).
- [x] Phase 4: advisory surfaces live (log-only). `ACTION_JUDGMENTS` (allow/ask/block + risky), `DecisionGateAudit`, `observe_gate` wired into `sandbox_gate.evaluate_tool_call` (both return paths, deterministic 10% sample, 0.5s budget, never perturbs decisions). Turn calibrator gained `--join-facts` (would-skip precision/coverage vs TurnFact per execution_id). Live: read→allow 0.49 agree; DROP TABLE→block vs sandbox allowed (divergence captured, ollaya conf only 0.14); fact join query proven (n=3, vacuous precision 1.0 — needs volume).
- [x] Phase 5: certification machinery live (nothing certified — all HOLD on volume, honest). `DecisionAutomationAction` ledger, `decision_automation.py` (status off/collecting/ready/enforced, automation pass, resolve with env-wins + revoke-beats-certify, pure act-rules), `ATOM_DECISION_AUTO_ENFORCE` + `ATOM_OLLAYA_INTENT_ACT_THRESHOLD` flags. Live: status collecting (15/3/7 rows), pass → no actions, approve→resolve True round-trip verified. No prod path acts on ollaya output yet — that flip waits for certified thresholds at volume.
- [x] Phase 6 (integration, switched ON in dev 2026-09-25): `GET /health/decision-router` public route; shadow flags enabled in gitignored `backend/.env` (master + all 3 shadows, gate sample 1.0 for measurement); backend restarted; real agent run → turn row in dev DB (`task_done` 0.72, `stuck` 0.04, 853ms). Enforcement stays OFF everywhere.

## Live learnings (do not regress)

1. HTTP `/v1/systemone` + `/api/decide` require explicit `questions` — presets are CLI/MCP-only. `decide()` routes preset→`ollaya run --preset` subprocess, questions→HTTP.
2. Cold model load (~4-5s) exceeds the 0.8s inline budget. Inline callers keep 0.8s (skip on cold); shadow passes `timeout_s=30`. Dead server → fallback/breaker (correct, verified).
3. Early shadow signal (n=3, heuristic incumbent — no LLM keys in this env): 1/3 agreement; disagreements carried low confidence (0.303/0.533), Brier 0.136. Tune criteria only after volume; compare vs real LLM where keys exist.
4. Real LLM comparison (OpenCode Go key, n=6 intent battery): 3/6 agreement; ollaya over-predicts `workflow` (chat 1/4, task 0/2, workflow 3/3). BUT the t=0.6 act-rule is 4/4 precise at 44% coverage (n=9) — calibration works, coverage is the cost. Brier 0.129.
5. Incidental find: `IntentClassifier._llm_classify` called `self.llm.call(...)`, which does not exist on `LLMService` — the LLM path was dead in production, heuristic silently served everything. Fixed to `generate_completion` (+24 test mocks); now the shadow compares against the real incumbent.
6. Gate shadow (n=3): verdict direction right (allow read, block DROP TABLE + student email) but confidences flat (0.14 floor on block, risky insensitive to SQL severity). Small-model signal or state-format issue — needs volume + review of divergences. Certify gates against `write_violation` rows + human-reviewed divergences, NOT raw agreement (sandbox default-allows, so agreement mostly measures sandbox permissiveness).
7. Cold model kills hot-path telemetry: 0.5s gate budget abstains until warm. Production needs `OLLAYA_KEEP_ALIVE` high (30m) + warmup at daemon start; sampled coverage (not completeness) is the correct expectation.
8. Pre-existing failure (not ours): `test_sandbox_policy.py::test_S4_tier_floor_monotonic` fails on pristine tree too — verified via stash.
9. Schema lesson: `DecisionGateAudit` shipped without the `surface` column (counts silently read 0 — the read-path guards hid it). Fixed with model column + self-healing ALTER + NULL backfill on the write path, plus a legacy-table test. Rule: every new audit table gets a surface column from day one, and counts should log (not just swallow) filter errors.
10. Gate certification needs violation-join ground truth (`write_violation` rows + human-reviewed divergences), not raw agreement — sandbox default-allows. Turn pre-filter needs facts-per-execution at volume. Both joins are built; volume is the only missing ingredient.
11. Integration bugs found live (both fixed): (a) turn hooks reused the extractor's `digest_parts`, which is undefined when `TURN_FACT_EXTRACTION_ENABLED=false` (dev `.env` line 77) — silent NameError, zero rows. Hooks now build their own digest via `build_turn_digest`. (b) meta session-end hook sat INSIDE the extraction flag — moved out. Rule: shadow hooks never depend on another feature's flag or locals.
12. `IntentClassifier` (CHAT/WORKFLOW/TASK) has NO live callers — chat uses `classify_intent_with_llm` (25+ action intents), meta-agent routes queen/fleet elsewhere. Intent shadow is integrated but dormant; next step is routing the queen/fleet choice through it, or retiring it. Turn + gate shadows collect live now.

## Risks / guardrails

- Maturity risk (upstream ~138★): pin `ollaya` version + model commit sha; abstract behind `DecisionService` so fallback = current behavior; kill switches `ATOM_OLLAYA_ENABLED` / `ATOM_OLLAYA_FORCE_ENFORCE=false`.
- Threshold drift: never hard-enforce without calibration run; revocation automatic.
- Voice inline latency: keep Ollaya off the STT→TTS hot path until GPU numbers prove out; cron/agent-loop only at first.
- Security: question sets are code-reviewed (no prompt-injected `instructions`); decision never bypasses P2/P9/sandbox/ego gates — it only proposes.
