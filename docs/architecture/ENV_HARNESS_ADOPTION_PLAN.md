# Evolving-Environment Curriculum — EnvHarness Adoption Plan

> **Status:** CLOSED 2026-09-21 (rev 4 corrections applied — see
> Corrections). Phases 1–3 IMPLEMENTED and retained. Phase 4 executed per
> registered design → STOP (+12.5pp < +15pp). Phase 4b replication: **no
> observed advantage** (arm A 6/6 and arm B 6/6 on fresh instances — both
> arms at ceiling; the 12/12 ceiling check shows the tasks were solvable at
> test time but does not fully exclude drift) → **FINAL STOP**: benefit not
> demonstrated at the tested budgets, and no further investment is
> warranted under this design. The causal story of the 4a delta remains
> unknown. Rev 2 narrowed the original proposal after a code-level review;
> rev 3 records the build + both runs; rev 4 corrects the scientific
> claims, the failure classification, and the audit trail.
> **Added:** Sep 21, 2026 (ZCode, from VentureBeat coverage + upstream repo read)
> **Sources:** google-research/envharness (Apache 2.0, arXiv:2608.19880) —
> [GitHub](https://github.com/google-research/envharness),
> [arXiv](https://arxiv.org/abs/2608.19880),
> [VentureBeat article](https://venturebeat.com/orchestration/googles-open-source-envharness-lets-ai-agents-train-against-environments-that-evolve-with-them)
> **Cross-references:**
> [`HARNESS_EVOLUTION.md`](./HARNESS_EVOLUTION.md) (the agent-side twin of this plan),
> [`AGENT_HARNESS_RESEARCH.md`](./AGENT_HARNESS_RESEARCH.md) §5 (sandboxing + outcome verification),
> [`AGENT_ENVIRONMENT.md`](./AGENT_ENVIRONMENT.md) (goal predicates),
> [`GOAL_RUN_ORCHESTRATION.md`](./GOAL_RUN_ORCHESTRATION.md) (criterion evaluator)

## TL;DR

Atom's self-evolution machinery is pointed entirely at the **agent** (harness
micro-patches, Memento skills, WikiSkill patterns, playbook drafts). Google's
EnvHarness shows the complementary move: point the same
observe → diagnose → mutate → validate loop at the **environment**, while
freezing the trusted verifier. The raw materials all exist here — trajectory
capture, deterministic verifiers, a hermetic eval site, an isolated sandbox, a
governance-gated promotion path — **but four of them are not currently safe to
build on** (the sandbox falls open to a host subprocess; two verifiers check
subsets of their tasks; the eval site has no mutation boundary; the
distiller's eligibility rules don't accept synthetic traces). This plan
hardens those first, then proves the central assumption — that training
trajectories from mutated environments produce *transferable* learned
artifacts, not answer memorization — with one environment adapter and a few
hand-authored mutations, in an equal-budget controlled experiment. The
designer loop and everything downstream are built **only if that experiment
wins**. No RL, no weight training; the payoff is a curriculum generator for
the distillation pipelines that already exist.

## What EnvHarness does (upstream facts)

- Wraps a static environment behind `ActionableEnv` (`reset/step/observe/
  evaluate`, plus `save_state`/`from_state` for cheap reset) and stacks
  three mutation layer types, each accepting a config plus **code-as-mutation**
  executed in an isolated subprocess:
  - `Setup` — changes the starting state (hide the target object; pre-complete
    early steps; variant goals).
  - `Rules` — changes the interaction contract: act on `step()` (drop actions,
    inject tool errors) and on `observe()` (filter/alter what the agent sees).
  - `Link` — chains task configs into longer trajectories (goal preservation,
    action budgeting).
- A **designer agent** ("EnvRigger" in coverage; the repo ships
  `designer_agent.py`) loops: run the agent → observe trajectories → diagnose
  recurring failure modes → compose new layers → **validate** the mutation is
  useful and the environment still solves (upstream: 5 rollouts original +
  5 fresh rollouts mutated, up to 5 write-validate iterations). The paper
  reports gains of **up to ~9 points** on held-out tasks (not an average)
  across ALFWorld, WebArena, SWE-bench Verified, OfficeQA, SpreadsheetBench,
  paired with ReasoningBank-style skill extraction.
- Two hard invariants worth importing wholesale: **the verifier/grader is
  never mutated**, and admitted mutations must land in a **difficulty band**
  (upstream ≈ 0.4–0.6 success) — trivially-passed and never-passed candidates
  are discarded.

## Readiness corrections (rev 2 audit — what rev 1 got wrong)

Rev 1 declared "no verifier gap" and treated the sandbox and bridges as
free. Verified against source on 2026-09-21:

1. **The sandbox falls open, not closed.**
   `core/auto_dev/container_sandbox.py:102-108` silently falls back to
   `_execute_subprocess` (line 218) — host `python3`, inherited environment,
   full filesystem and network access; rlimits (line 288) are best-effort and
   POSIX-only. Any promise of "runs only in the sandbox" is false on any host
   without Docker. Generated mutations must require fail-closed container
   execution.
2. **Two of the eight verifiers are incomplete, and evidence shares a dict
   with world state.** `tasks.py:38-41` (`form_fill`) checks only the name
   field and submission count — email/company outcomes unverified;
   `tasks.py:89-94` (`form_validation`) checks only an error counter,
   ignoring the requested report. All of it reads the same module-global
   `STATE` (`test_site.py:17`) that a Setup mutation would manipulate, so a
   mutation touching `STATE["form"]` can manufacture passes **without
   touching verifier code** — freezing these verifiers as-is would freeze
   the hole.
3. **The site has no mutation boundary.** Page content (`DOCS`, `CREDS`, the
   headline, the long-page code) is hardcoded in handler bodies outside
   `STATE` (`test_site.py:26-37, 60-109`); the only external surface is a
   read-only `GET /state`. `STATE` is module-global and the runner resets it
   in-process between sequential tasks (`run_eval.py:37`) — no concurrency
   isolation. And the runner drives `OperatorLoop` with a vision decider
   (`run_eval.py:34-46`), not the chat planner.
4. **The distiller is not "just another trace source."**
   `knowledge_pattern_service.py:200-227` samples `AgentEpisode` rows;
   passing traces require `supervisor_rating >= 4`, and `_trace_view`
   (line 183) carries no action/observation sequence at all. Verifier-passing
   synthetic episodes cannot substitute for human ratings without a decision,
   and silently mixing them into the ordinary corpus would contaminate
   graduation evidence.
5. **Fixed answers everywhere** (`ATOM-7741`, `quokka`, `LONGPAGE-99`, the
   headline): repeated training runs against these eight tasks risk teaching
   answer memorization, not skill. Held-out evaluation requires task
   **families** with disjoint instance values.

What genuinely is ready: trajectory capture (`AgentReasoningStep`, episodes),
the auto_dev loop shape (reflection → mutation → regression validation →
governance/rollback), the rollout budget discipline, and the operator_eval
site as a deterministic base environment with a baseline runner that already
prints a per-task table (`run_eval.py`).

## What we are deliberately NOT doing

- **No RL / weight training.** Upstream's GRPO adapters are irrelevant;
  Atom's "learning" is skill/memory induction. We want the curriculum +
  validation discipline, not the trainer.
- **No live-integration environments.** Mutations run only against hermetic
  surfaces. All harness scripts run with `TESTING=1` / scratch
  `DATABASE_URL`; the incident-eval runner's purity rule is the model.
- **No host-subprocess execution of generated code, ever** (see Phase 1a).
- **No Link layers, no incident-eval bridge, no chat-planner adapter** until
  the Phase 4 experiment justifies them (deferred, see Phase 5).
- **No dependency on the upstream package.** Our environments are services
  and snapshots, not gym envs; a thin native interface mirroring the
  `Setup`/`Rules` semantics is cheaper than a Bridge per environment.

## Plan (rev 2 sequence)

### Phase 1 — Harden the prerequisites (blocking, no curriculum work)

**1a. Fail-closed mutation sandbox.** New execution path for generated
mutation code that *refuses* to run when Docker is unavailable (raise /
return `environment_refused`), never falling back to
`_execute_subprocess`. Keep today's `ContainerSandbox` for its existing
auto_dev callers; the new `FailClosedMutationSandbox` (wrapper or
constructor flag) is the only executor mutations may use. Tests: (i) monkeypatch
`docker_available=False` → mutation execution is refused and nothing ran;
(ii) a mutation that attempts filesystem/network/host-env reads fails inside
the container; (iii) existing auto_dev behavior unchanged.

**1b. Split world state from execution evidence on the eval site; strengthen
the two weak verifiers.** `test_site.py` grows two namespaces: `WORLD`
(mutable content: docs text, credentials, headline, long-page code, search
corpus, form field labels) and `EVIDENCE` (append-only, verifier-owned:
submissions, errors, logins, visited list). Mutations may load `WORLD`; the
mutation API cannot name `EVIDENCE` (enforced at the API, tested).
`form_fill` verifies all three submitted fields + count; `form_validation`
verifies the error count **and** that the summary reports the actual error
text. All eight verifiers re-reviewed field-by-field before anything is
declared frozen. Unit tests pin each strengthened check against real
submissions.

### Phase 2 — One complete adapter (operator_eval site ↔ OperatorLoop)

The mutation boundary is real work, not an interface sketch:

- **Site control API**: `POST /control/reset`, `POST /control/load_world`
  (WORLD only), `POST /control/rules` (declare observation/action filters),
  bound to 127.0.0.1, authenticated by a per-run token, pages rendered from
  `WORLD` (content moves out of handler bodies). Rules hooks implement the
  upstream `Rules` semantics: act on responses (filter/alter observation
  HTML) and on requests (404/redirect an action, inject a tool-visible
  failure).
- **Agent boundary**: the adapter drives `OperatorLoop` (the existing eval
  subject — real Chromium, vision decider), passes the run token, and
  records per-step action traces (action type, success, navigated URL /
  page title where the backend reports them). Observation capture (page
  text/screenshots per step) is NOT built — flagged as open work, since the
  loop-side hook for it doesn't exist yet; distillation consumers must not
  assume observations are present (see Corrections #3).
- **Concurrency/isolation**: one site instance per run on an ephemeral port
  (STATE is module-global today); no shared process between arms.
- **Outcome taxonomy**: every rollout returns `pass` | `agent_fail` |
  `harness_error` (provider 401/402/timeout, loop crash, control-API
  failure). Harness errors are excluded-and-rerun, never counted as agent
  failures — the current `run_eval.py` "harness error" row is the precedent;
  the taxonomy becomes structural in the adapter's return type, echoing the
  repo's `verified` tri-state culture.

Exit criteria: a fresh checkout runs the 8 tasks N=5 through the adapter with
zero harness errors unclassified, and the baseline table lands in this doc
(pinned model — see Phase 4; note the 2026-09-21 provider situation in the
coordination log: deepseek is the only healthy provider; pin explicitly).

### Phase 3 — Hand-authored declarative mutations (no designer loop yet)

A small library of human-written `Setup` and `Rules` mutations expressed as
declarative configs against the control API — e.g. *hide the docs link from
the index*, *rename the form fields*, *inject a transient 500 on first
form submit*, *strip the credentials hint from the login page*. Each ships
with canary checks: (i) the **original** verifier still runs unmodified and
passes for a strong configuration (solvability), (ii) baseline-config success
moves (the mutation actually does something), (iii) `EVIDENCE` untouched
(structural, from 1b). This proves the machinery end-to-end and produces the
mutation vocabulary the Phase 5 designer would compose from — before any
automation exists.

### Phase 4 — Isolated, equal-budget learning experiment (the decision gate)

Pre-registered design, written into this doc **before** any run:

- **Task families**: each of the 8 tasks parameterized (codes, names,
  headlines, credentials, doc contents drawn from generated pools) with
  disjoint instance sets for train / validation / test. Training and
  evaluation never see the same answers — this is the memorization control.
- **Arms**: (A) static-environment baseline, (B) mutated-environment
  curriculum (Phase 3 library, sequenced). **Equal rollout allocation**
  across arms (actual cost — steps/tokens — is an outcome, not a
  construction); same pinned model and frozen routing (provider catalog
  snapshot, no runtime ladder drift); separate isolated stores per arm for
  learned artifacts (namespaced patterns/playbooks, synthetic provenance on
  every episode: env id, mutation stack, arm).
- **Distillation**: arm B's trajectories distill via a synthetic-only
  ingestion path. The ≥4 supervisor-rating gate is **not** satisfied by
  verifier success by substitution — for this experiment the evolver consumes
  the synthetic corpus directly (separate namespace); any later production
  use requires a supervisor-sampling/rating step before promotion. Synthetic
  episodes never enter ordinary graduation evidence.
- **Pre-registered thresholds** (fill in exact numbers at registration, do
  not tune after seeing results): minimum useful held-out improvement on test
  families (absolute pp on success rate), maximum cost multiple vs arm A,
  minimum instance count per family for the result to count.
- Trajectories needed by the distiller beyond `_trace_view`'s compact form
  (it omits actions/observations) are attached via the adapter's step log,
  keyed by episode id.

**Gate:** B beats A on test families at ≤ the cost multiple → Phase 5 is
worth building. Otherwise stop here, record the numbers, and keep the
hardened sandbox/verifiers (they were worth having anyway).

### Phase 5 — Designer loop (only if Phase 4 wins)

Now clone the auto_dev loop shape for environments: reuse
`reflection_engine`'s batching discipline and knowledge-pattern failure modes
as Diagnose; an LLM composes candidate mutations from the Phase 3 vocabulary;
validation = the rollout protocol below; admission = difficulty band. Only
at this point reconsider Link layers and the incident-eval bridge (each
production incident → a family of banded variants instead of one regression
case).

**Rollout protocol (replaces rev 1's 3-rollout band):** screening with 3
rollouts (cheap reject of trivial/impossible), then **independent
confirmation** with fresh rollouts (default 6, configurable) reporting a
Wilson interval on the success rate — band admission decided on the
confirmation set's interval, not the screening point estimate. Rationale: at
3 rollouts a genuinely 90%-solvable mutation qualifies in-band 27% of the
time, and ≤5 revision rounds amplify that selection noise; the two-stage
protocol plus uncertainty reporting keeps admitted mutations honest.
Harness errors are excluded and rerun (Phase 2 taxonomy), never silently
counted. Every admitted mutation gets a durable row: env id, layer config,
screening + confirmation outcomes with intervals, generating failure-mode
ids, rollout cost.

## Risks / costs

- **Compute:** rollouts dominate; the experiment budget is pre-registered in
  Phase 4 and the designer (if built) runs under auto_dev-style daily caps in
  sleep-time windows.
- **Provider fragility:** the 2026-09-21 fleet state (single healthy
  provider) makes "pin model + freeze routing" load-bearing, not ceremonial;
  a provider dying mid-experiment invalidates the arm — the taxonomy marks
  those runs, and the experiment resumes rather than mixes.
- **Determinism drift:** LLM agents are noisy; disjoint instance families and
  interval reporting are the mitigations. If family-level variance swamps the
  effect at the registered budget, the honest answer is "inconclusive at this
  cost," recorded as such.
- **Scope creep:** live integrations, Link layers, and the incident bridge
  stay out until the gate opens them.

## Coordination

When implementation starts: log the window in `notes/AGENT_COORDINATION.md`
(new package `backend/core/env_curriculum/` plus edits under
`backend/tests/operator_eval/` — the site/task edits in Phase 1b are shared
files, claim them explicitly), cite arXiv:2608.19880 in the first commit, and
keep baseline/experiment numbers in this doc — it is the decision record for
whether Phase 5 happens.

## Implementation record (rev 3, 2026-09-21)

Phases 1–3 shipped in one window (coordination log 2026-09-21 ~11:40 EDT).
All numbers below are from that window's test runs.

- **Phase 1a** — `core/env_curriculum/sandbox.py`:
  `FailClosedMutationSandbox` subclasses `ContainerSandbox` with the
  subprocess fallback removed: per-call fresh Docker probe (the parent
  caches), refusal raises `MutationSandboxUnavailable` when Docker is
  absent, `enable_network=True` is a constructor error, non-container
  results are refused (defence in depth against a future parent refactor),
  and successful runs carry an `isolation` attestation.
  `execute_mutation()` offers the structured `status="refused"` payload for
  batching callers. The parent class is untouched (existing auto_dev
  behavior unchanged). Tests prove no host fallback: refusal with
  `docker_available=False` while `_execute_subprocess` and
  `create_subprocess_exec` are tripwired.
- **Phase 1b** — `tests/operator_eval/test_site.py` rewritten as
  instance-based `EvalSite` (no module-global STATE): `WORLD` (mutable,
  `WORLD_SCHEMA`-enforced) vs `EVIDENCE` (append-only, verifier-owned);
  pages render from WORLD values (content moved out of handler bodies);
  `load_world_updates` structurally rejects evidence keys; `/control/*`
  token-gated. `tasks.py` verifiers now take `(result, site)` and read
  structured world ground truth + evidence: `form_fill` checks all three
  fields + count, `form_validation` requires the actual error message in
  the summary (read back from evidence, so copy mutations stay
  verifier-consistent). A regression test pins the exact rev 1 hole
  (missing email no longer passes).
- **Rollout protocol** — `core/env_curriculum/outcomes.py`:
  `RolloutStatus` taxonomy, `pass_rate` excluding harness errors, Wilson
  interval (boundary-pinned), two-stage `admit_mutation` (screen all-fail →
  impossible; confirmation must contain ≥1 pass and ≥1 fail — Wilson bounds
  exclude 0 and 1 — and its interval must overlap the band; refuses to
  decide without the full scorable complement of either stage).
  Honest caveat, documented in `BandSpec`: at the default confirm_n=6 the
  interval is wide, so the binding constraints are "neither trivial nor
  impossible"; the band endpoints become selective at larger confirm_n.
- **Phase 2** — `tests/operator_eval/adapter.py`: `EnvInstance` (ephemeral
  port + per-run token, one instance per rollout/concurrent arm) with
  `apply_stack` (validates before applying; raises, never partially
  applies), and `run_rollout` with the mechanical classification rule:
  any machinery exception → HARNESS_ERROR; loop completed + verifier
  rejects → AGENT_FAIL; accepts → PASS. The control API's token gate is
  pinned over real HTTP.
- **Phase 3** — `tests/operator_eval/mutations.py`: 12-stack library (7
  Setup rotations — which double as the Phase 4 family-parameterization
  mechanism — 2 positive Rules, 3 negative Rules), mechanical solutions for
  all 8 tasks, and `run_canary_suite()` asserting solvability direction +
  the world/evidence firebreak per run. One canary bug found and fixed
  during the build (the login solver's regex swallowed trailing HTML —
  exactly the class of bug the canaries exist to catch).
- **Verification:** 48/48 tests green on python 3.14 AND 3.11
  (`tests/test_env_curriculum.py` + `tests/operator_eval/test_env_site.py`).
  Adjacent suites run for regressions: test_covpush_autodev,
  test_skill_impact_ledger, test_tool_error_evolution,
  test_covpush_w96_core_batch7 → 314 passed; the 7 ServiceFactory failures
  in the last file reproduce on pristine HEAD in a throwaway worktree
  (pre-existing, unrelated). No server-path code touched; no backend
  restart needed; no live model rollouts run.
- **Known limitation carried forward:** the site serves world+evidence on
  `GET /state` to anything that can reach it (same surface the original
  harness had); per-family rules can `block_path /state`, and the Phase 4
  design decides this per task family.

## Phase 4 pre-registration (REGISTERED 2026-09-21, ZCode — best estimates per user directive; frozen before first experiment rollout)

> Registered with best estimates as directed. Any change after results are
> seen invalidates the run.

- **Date registered / registrant:** 2026-09-21, commit `7ff7377cf`
  (authored 12:29:03 EDT — before the registered run's first rollout at
  12:56; the "~16:40 EDT" time originally written here was wrong and is
  superseded by git — see Chronology). Registrant: ZCode.
- **Model pin:** `glm-5.3-flash` on opencode-go, called DIRECTLY via the
  handler's opencode-go client (`PinnedVisionDecider`, temperature 0.1,
  max_tokens 1024, one bounded parse-retry). Feasibility probe (2026-09-21):
  the LLMService ladder vision-gate-vetoes explicit opencode-go picks
  (pricing cache lacks vision flags for glm/qwen) and falls through to a
  402-dead openrouter rung — so a direct pinned client is also the only way
  to honor "frozen routing"; it is registered as such, not chosen as a
  workaround. Direct-call probe: glm-5.3-flash, deepseek-v4-flash-vision-exp,
  kimi-k3, mimo-v2.5 all accepted image content-parts; glm-5.3-flash pinned
  (fastest of the verified set).
- **Routing freeze:** by construction — one provider client, one model, no
  ladder. `OPENCODE_BASE_URL` = zen go endpoint (backend/.env, gitignored);
  catalog snapshot `data/provider_model_catalog.json` @ commit 510680552.
- **Families:** the 8 base tasks, each parameterized by its world knob
  (api_code / secret_word / longpage_code / creds / form_error_message /
  headline / form labels / doc titles). Value pools hardcoded in the runner,
  seed 20260921: train pool disjoint from test pool; both disjoint from base
  values (base answers are the memorization trap). Pools: train 2 values,
  test 2 values per family.
- **Instances:** per family — arm A train: base ×2 (16 rollouts); arm B
  train: base + train-rotated (16 rollouts). Test: train-rotation-disjoint
  rotated values, same instances both arms (16 rollouts/arm). Total 64
  rollouts + 16 distillation calls. `max_steps` 15 (smoke showed 12 too
  tight for scroll-heavy tasks; 15 = run_eval default).
- **Arms:** A = static base env (status quo); B = mutated curriculum
  (train-rotated instances from the Phase 3 Setup vocabulary).
- **Learned artifact + application:** per family per arm, ONE strategy
  brief (≤1200 chars) distilled by the same pinned model from that arm's 2
  train trajectories (text-only call; distiller instruction: "transferable
  procedure, not one-off answers — values change between instances",
  identical for both arms). Applied at test as a goal prefix marked
  "[Strategy notes from an earlier practice session — values may differ]".
  No DB writes anywhere in the experiment (nothing enters episodes/
  graduation evidence; synthetic-corpus separation satisfied vacuously and
  by construction).
- **Primary metric:** test-family success rate (frozen verifier), arm B −
  arm A on the pooled 16 test rollouts per arm.
- **Minimum useful improvement:** +15pp absolute (≥ 2.4/16 → in integer
  terms ≥ 3 rollouts). **Cost control:** equal rollout ALLOCATION (16 test +
  16 train per arm) — NOT a guaranteed equal cost: step counts, retries, and
  token usage are per-arm outcomes, not construction. Measured after the
  run: arm A 301 steps vs arm B 275 across the 32 rollouts each; tokens
  were not metered per arm (marginal cash ≈ 0 on the Go-plan subscription).
  **Minimum instances for the result to count:** 16 test rollouts per arm
  (2/family × 8).
- **Harness-error budget:** each harness error rerun up to 2× (reruns don't
  consume budget slots); abort the stage if > 25% of its rollouts remain
  harness errors after reruns. **Wall-clock cap:** 3.5h total; checkpoint
  results to disk after every rollout.
- **Decision rule:** B ≥ A + 15pp on test families → Phase 5 designer loop
  is justified. Else stop, record numbers here, keep the Phase 1 hardening.
- **Pre-registration sanity (observed before registration):** pinned smoke
  on `find_code` base env — agent_fail, 12 steps, 64.1s: the trace shows
  the model looping on a nonexistent `/docs` index URL (genuine agent
  failure; the exact class a procedure brief should fix). Per-task success
  rates are therefore expected in a low-to-mid band — suitable for the
  band protocol, and confirmation that the test cannot trivially saturate.

## Results (2026-09-21, registered run checkpoint `experiment_20260921-125616.json`, final write 13:48 EDT — decision: STOP)

Full registered run executed as designed: 64 rollouts + 16 distillation
calls, **zero harness errors as classified at the time** — see Corrections:
the classification in place during this run could not reliably distinguish
infrastructure failures from agent failures (both the decider's
provider-failure path and the loop's internal exception handling could
launder harness problems into agent outcomes), so read this as "no harness
problems surfaced", not a verified absence. Both arms 8/16 at train; wall
clock ~52 min (well under the 3.5h cap). Checkpoint:
`tests/operator_eval/results/experiment_20260921-125616.json` (gitignored;
kept locally).

| | test_A (static) | test_B (curriculum) |
|---|---|---|
| **Total** | **6/16 = 37.5%** | **8/16 = 50.0%** |
| find_code | 2/2 | 2/2 |
| search_and_click | 0/2 | 0/2 |
| scroll_find | 2/2 | 2/2 |
| login_flow | 0/2 | 0/2 |
| form_validation | 0/2 | 0/2 |
| extract_headline | 2/2 | 2/2 |
| form_fill | 0/2 | 0/2 |
| ordered_navigation | **0/2** | **2/2** |

**Delta +12.5pp — below the registered +15pp threshold → STOP.** The
designer loop (Phase 5) is not justified at this budget with this pin.

Reading the result honestly:

- **The entire delta is one family.** `ordered_navigation` is the cleanest
  signal in the dataset FOR the hypothesis: arm A passed both train rollouts
  on base titles, then failed both title-rotated test instances (its brief
  had memorized base-value-dependent navigation), while arm B — trained on a
  rotated instance — passed both. That is memorization-vs-transfer behaving
  exactly as theorized, but on n=2; it is anecdote, not a demonstration.
- **Floor families dominate the pooled rate.** Four of eight families
  (form_fill, form_validation, login_flow, search_and_click) went 0/4 per
  arm across train+test: `glm-5.3-flash` cannot reliably ground clicks/keys
  on this viewport. Strategy briefs cannot fix an execution deficit — the
  bottleneck there is the model's actuation, not its knowledge. With half
  the families floored, the pooled delta mathematically cannot reach the
  threshold even if the curriculum effect is real on knowledge-limited
  families.
- **Where the model already has grounding, ceiling effects dominate**
  (find_code/scroll_find/extract_headline 2/2 for both arms — nothing for a
  brief to add).

Verdict for the record: the registered experiment produced a directionally
positive but under-threshold result whose entire signal sits in one n=2
family — and whose briefs were induced from LOSSY trajectory summaries
(action types + success flags + truncated final summary; no observations,
parameters, or intermediate reasoning — see Corrections), so what failed to
clear the bar here is specifically *brief induction from lossy summaries*.
A future attempt — new registration, not a modification of this one —
should pin a stronger-grounding computer-use model, restrict families to
knowledge-limited ones, pre-register per-family scoring as primary, and
feed the learner full action/observation trajectories.

What stands regardless of the verdict: the Phase 1 hardening (fail-closed
sandbox, world/evidence split, strengthened verifiers, the pinned-decider
harness, the two-stage admission math) is durable infrastructure, exactly as
the registered decision rule anticipated.

## Phase 4b registration (NEW registration, commit `45248701d`, authored 15:36:45 EDT — a replication test; the 4a STOP stands in the record)

This is not a modification of the 4a verdict — it is a separate, narrower
experiment answering the one question 4a left open at actionable n: does the
ordered_navigation memorization→transfer result replicate with more
instances under the same design? Family selection rule (registered): the
4a variance class (≥1 pass AND ≥1 fail across all 4a rollouts) — computed
from the 4a checkpoint BEFORE this registration — contains exactly one
family: ordered_navigation (trainA 2/2, testA 0/2, trainB 2/2, testB 2/2).

- **Pin/routing:** unchanged from 4a (glm-5.3-flash direct client; the only
  verified vision-capable pin on the healthy fleet — glm-5.3 and qwen3.8-max
  reject image parts, deepseek is text-only).
- **Arm A train:** base ×2. **Arm B train:** base + train-rotated (same
  train pool as 4a). Test: SIX rotated title-sets per arm, disjoint from the
  train pool (fresh values registered in the runner).
- **Budget:** 4 train + 12 test rollouts = 16 (ordered_navigation), plus a
  NON-DECISIONAL ceiling-stability check: the three 4a ceiling families
  (find_code, scroll_find, extract_headline) run test-only with bare goals,
  2 instances × 3 families × 2 arms = 12 rollouts. Total 28.
- **Primary endpoint & decision:** B − A ≥ **33⅓pp** on the 12
  ordered_navigation test rollouts (a 2-rollout gap out of 6; the
  "≥34pp" originally written here over-rounded and is corrected) → the 4a
  result REPLICATES, and the Phase 5 designer loop is justified
  **narrowly**: for variance-class families only, each gated on a
  4a/4b-style variance classification before any run. Anything else →
  final STOP (benefit not demonstrated; no further investment under this
  design). Registration discrepancy acknowledged: the runner's printed
  decision at run time still applied the 4a 15pp rule (then hardcoded);
  the outcome is identical under either rule (observed delta 0pp), and the
  runner now takes the threshold as an explicit recorded parameter.
- **Non-decisional check:** ceiling families should stay ≥ 5/6 per arm
  pooled; a collapse there means the pin/environment drifted and the
  primary result is suspect (record, don't decide).
- **Everything else** frozen from 4a: rerun discipline, wall-clock cap
  (1.5h here), checkpointing, no DB writes, scratch DATABASE_URL only.

## Phase 4b results (commit `191b944bc`; primary checkpoint `experiment_20260921-153650.json`, ceiling-check checkpoint `experiment_20260921-154716.json` — decision: FINAL STOP)

The replication found **no observed advantage**: on six fresh rotated test
instances of ordered_navigation, arm A — the arm that had failed these in
4a — passed 6/6, and arm B also passed 6/6 (both arms at ceiling). Delta
0pp against the 33⅓pp bar. The registered non-decisional ceiling check
passed 12/12 (find_code, scroll_find, extract_headline, bare goals): this
shows the tasks were solvable and the pin servable at test time, but it
cannot fully rule out model/environment drift between and within runs.

Conclusion: the 4a ordered_navigation difference did not replicate —
**no benefit was demonstrated at the tested budget**. Whether the 4a delta
was stochastic variance, drift, or something else cannot be determined
from these runs; both recordings are preserved as they were observed. Per
the 4b rule ("anything else → final STOP"), the investment decision is
FINAL STOP for this design; the causal attribution of the 4a delta is
left explicitly open.

What the two runs established, for whoever revisits evolving-environment
ideas here:

1. The hardening (fail-closed sandbox, world/evidence split, strengthened
   verifiers, adapter taxonomy, Wilson admission protocol) is retained and
   is useful for ANY future eval work, not just curricula. Caveat
   (Corrections): during these runs the harness-error classifier was
   partially blind — provider failures could surface as `done=True` from
   the decider and loop-caught errors scored through the verifier — so
   the "zero harness errors" observations are not reliable measurements.
   The classifier has been fixed (decider raises on provider failure; the
   adapter classifies error-bearing results as HARNESS_ERROR) and is
   test-pinned for future use.
2. The pipeline (register → mechanize → execute → replicate) works and is
   cheap: 92 rollouts across the registered runs (64 + 16 + 12, excluding
   distillation calls and the three preliminary find_code dry runs), ~90
   minutes of wall time, marginal cash ≈ 0.
3. glm-5.3-flash's pass/fail behavior on this site varies materially
   across sessions (the same task was observed at 0/2 and 2/2 in
   different runs), so small-n agent comparisons on this pin are fragile.
   Future work must either pin a more deterministic model, raise n
   substantially, or measure within-session. That is a property of the
   subject, not of the curriculum.
4. Per the original framing: the honest negative is the deliverable. No
   Phase 5. No further registrations under this design.

## Corrections (rev 4, 2026-09-21 — after external review of the experiment record)

1. **"Zero harness errors" was not a reliable measurement.**
   `PinnedVisionDecider` converted exhausted provider failures into a
   synthetic `done=True` decision, and `OperatorLoop` catches its own
   exceptions internally, returning them in `result["error"]` — which the
   adapter then scored through the verifier. Infrastructure failures could
   therefore be recorded as agent failures (or, with a lucky verifier,
   passes). Fixed: the decider now RAISES on provider failure (the loop
   records `error=`), and the adapter classifies any error-bearing result
   as HARNESS_ERROR before the verifier runs — both test-pinned. The 4a/4b
   "zero harness errors" observations are the pre-fix classifier's output
   and should be read as "none surfaced", not verified absence.
2. **"Mechanism refuted" overstated the evidence.** 6/6 vs 6/6 at ceiling
   establishes no observed advantage on the replication — nothing about
   WHY the 4a delta appeared or disappeared. The record now says: benefit
   not demonstrated at the tested budget; the causal attribution of the
   4a delta is open. The investment decision (FINAL STOP) is unchanged.
3. **The learner never received full trajectories.** The Phase 4 design
   promised action/observation logs; `_distill()` actually received action
   types, success flags, navigated URL/title where present in the step
   detail, and a truncated final summary — no observations, parameters, or
   intermediate reasoning. These experiments therefore tested *brief
   induction from lossy summaries*, which narrows the negative result's
   scope. The runner now feeds the richer trajectory rendering for any
   future run; the observation-capture gap in the adapter remains open
   work (it requires loop-side changes and was not built post-STOP).
4. **Chronology (canonical — git commit times and checkpoint mtimes; the
   approximate EDT times in earlier sections and the coordination log are
   superseded):**
   | When (EDT) | What | Identifier |
   |---|---|---|
   | 12:01:52 | Phases 1–3 implementation | commit `510680552` |
   | 12:29:03 | **Phase 4 registration (before any registered rollout)** | commit `7ff7377cf` |
   | 12:34–12:53 | three preliminary find_code dry runs (unregistered; incl. the stack-typo and empty-brief fixes) | checkpoints `…-123046/-123521/-124415.json` |
   | 12:56–13:48 | **registered 4a run** (64 rollouts + 16 distills) | checkpoint `…-125616.json` |
   | 13:55:11 | 4a results recorded | commit `949eb2de5` |
   | 15:36:45 | **Phase 4b registration (before the 4b run)** | commit `45248701d` |
   | 15:42 | 4b primary (16 rollouts, ordered_navigation) | checkpoint `…-153650.json` |
   | 15:50 | 4b ceiling check (12 rollouts, test-only, bare goals) | checkpoint `…-154716.json` |
   | 15:51:46 | 4b results recorded | commit `191b944bc` |
   | 16:03:26 | computer-use evidence restriction (separate work, same day) | commit `cc4949377` |
   Total registered-run rollouts: **92** (64 + 16 + 12); preliminary runs
   (22 rollouts) and distillation calls are excluded from that total.
5. **Replication threshold arithmetic:** a 2-rollout gap out of 6 is
   33⅓pp; the registration's "≥34pp" over-rounded and is corrected above.
   The runner printed the 4a 15pp rule at 4b run time (then hardcoded);
   the decision is threshold-invariant here (0pp observed). The runner now
   takes `--delta-threshold` as an explicit, recorded parameter.
6. **Equal cost was claimed; equal allocation was delivered.** Equal
   rollout counts do not equalize step counts, retries, or tokens.
   Measured: 4a arm A 301 steps vs arm B 275; 4b primary 33 vs 32; ceiling
   check 15 vs 28. Tokens were not metered per arm. All cost language in
   this record now reads "equal rollout allocation".
