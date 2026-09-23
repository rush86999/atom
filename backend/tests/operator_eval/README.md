# Operator Eval Harness

Measures computer-use operator quality (model × loop × browser) against a
deterministic local site — success rate, steps, wall time per task. This
is the repo-standard evidence base (AGENTS.md §2: "measure, don't guess")
for model-pool and loop changes; numbers go in the commit/PR message.

Since the EnvHarness adoption (docs/architecture/ENV_HARNESS_ADOPTION_PLAN.md,
rev 2) this directory is also the first **mutable environment**: the site
splits mutable WORLD content from verifier-owned EVIDENCE, exposes a
token-authed control API, and carries a library of hand-authored declarative
mutations with deterministic solvability canaries.

## Running

```bash
cd backend
BROWSER_ALLOW_PRIVATE_ADDRESSES=1 \
ATOM_COMPUTER_USE_MODEL=gpt-6-astra \
python tests/operator_eval/run_eval.py --model gpt-6-astra
```

- `BROWSER_ALLOW_PRIVATE_ADDRESSES=1` — required: the eval site serves on
  127.0.0.1 and the browser SSRF guard blocks loopback by default. This
  flag is the explicit local-testing opt-in; never set it in production
  deployments.
- `--model` — any computer-use-capable model the BPC router serves
  (gpt-6-astra, claude-sonnet-4-6, claude-opus-4-6, computer-use-preview).
  Needs the provider's key (BYOK or env).
- `--only task_id,task_id` — subset runs while iterating.
- `--max-steps N` — step budget per task (default 15).

The runner needs no DB and never touches the live dev world. Each run gets
its own `EvalSite` instance on an ephemeral port (there is no module-global
state anymore), and every task starts from `POST /control/reset`.

## Tasks (8)

| id | verifies |
|---|---|
| form_fill | all three requested fields + exactly one submission recorded server-side |
| find_code | information retrieval: secret code reported in summary |
| login_flow | credential login → protected dashboard reached |
| search_and_click | search results navigation + content extraction |
| ordered_navigation | multi-page link following in order |
| extract_headline | reading specific content |
| scroll_find | scrolling to content below the fold |
| form_validation | error response read AND its actual message reported |

Verification reads the site's protected EVIDENCE (append-only execution
facts: submissions, errors, logins, visit order) plus WORLD ground truth.
A lying summary can't pass, and `form_validation` requires the agent to
report the error message the page actually showed.

## Architecture (rev 2 hardening)

- **WORLD vs EVIDENCE** (`test_site.py`): `WORLD` is the mutable content
  (page copy, codes, credentials, search results, form labels); `EVIDENCE`
  is append-only and owned by the verifiers. `POST /control/load_world`
  structurally rejects anything outside `WORLD_SCHEMA` — a mutation cannot
  manufacture passes through the evidence channel. Enforced by tests.
- **Control API** (token `X-Run-Token`; agent-facing pages never need it):
  `/control/reset`, `/control/load_world` (world keys only),
  `/control/rules` (declarative observation filters + action interceptors),
  `/control/state` (read-only view). `GET /state` returns world+evidence.
- **Rules engine**: `hide_link`, `redact_text` (observation side, applied at
  render time); `block_path`, `fail_first_n` (action side, intercepts before
  routing — blocked attempts leave no evidence). Unknown kinds/params → 400.
- **Adapter** (`adapter.py`): one `EnvInstance` (ephemeral site + token) per
  rollout; drives `OperatorLoop` and classifies every rollout as
  `pass` / `agent_fail` / `harness_error`. The loop reports WHY it ended
  via the typed `termination_reason` on its result (2026-09-22):
  `exception` / `observation_failed` / `stopped` are infrastructure and
  classify HARNESS_ERROR — excluded from rates and rerun, never counted as
  an agent failure — while `no_valid_action` / `unparseable_step` /
  `repeated_action_failure` / `action_blocked` / `budget_exhausted` /
  `completed` are agent-attributable and are scored by the frozen verifier.
  Executed entries carry the actual action `parameters` (coordinates, typed
  text, selectors) plus navigated URL/title.
- **Mutations** (`mutations.py`): declarative `MutationStack`s (Setup =
  world updates; Rules = observation/action specs) validated against the
  site schema, plus mechanical solutions (scripted solvers reading the same
  filtered HTML a browser sees) and canaries that assert solvability
  direction — positive stacks must stay solvable, negative stacks (rules
  that destroy a task's solution) must be DETECTED as unsolvable. The
  canary suite runs with no model, no playwright, no DB:
  `python -c "import sys; sys.path.insert(0,'tests/operator_eval'); from mutations import run_canary_suite; print(run_canary_suite())"`

Test coverage for all of the above: `backend/tests/test_env_curriculum.py`
(core sandbox/admission primitives) and
`backend/tests/operator_eval/test_env_site.py` (site, adapter, canaries).

Eval-integrity note: `GET /state` exposes world+evidence to anything that
can reach the site — the same surface the original harness had. A rules
stack can `block_path /state` if a task must forbid it; the Phase 4
experiment design decides this per family.

## Interpreting

- `pass` requires the verifier, not the loop's own `done` flag — a model
  that declares victory without doing the work fails.
- `steps` near the budget with low pass rates = the model is lost; a
  harness bug usually shows as uniform failures with `done=false`.
- Compare at least two models before changing the default; record the
  table in the PR.
- For curriculum work, prefer `adapter.run_rollout` over this CLI: it
  returns the classified outcome objects the Phase 4 experiment and the
  screen/confirm admission protocol (`core.env_curriculum.outcomes`)
  consume.
