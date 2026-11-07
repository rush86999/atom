# BROWSER_ACCEPTANCE_PLAN.md — ordinary-browser proof for TASK-WAIT-01

**Status: PREPARATION ONLY.** No world was launched, no application server was
started, no browser was driven, and no model/provider/account/credential action
was taken while writing this plan. The actual capture remains root-owned and
must be run separately.

**Purpose.** Define the smallest ordinary-browser acceptance that proves the
Agents page keeps one admitted job alive across an information wait, a real
backend/frontend restart while waiting, a page reload, a second missing-fact
question, and a real registered `tasks.create` effect verified by the default
oracle. The proof must not be satisfiable by an HTTP 200, a model sentence, a
hand-written plan, or a patched job row.

---

## 1. Frozen source and identity

Capture **only** from:

- Commit: `17b80d0deecedbb18fa21c59e5c27dad53c2174a`
  (root-integrated PR735 head, child of the admitted-scope hardening
  `8202c0173`).
- If root re-resolves a successor, record the new SHA and use that SHA for every
  artifact. Never mix two source revisions in one capture.

Do **not** capture from the branch that carries this plan
(`codex/generic-information-ui-20261107`, preparation head `88c38a5b5`). At
preparation time the local product delta against the frozen head was:

```text
backend/api/agent_routes.py | 214 +++++++++++++++++++++++++++++----------------
1 file changed, 15 insertions(+), 199 deletions(-)
```

That delta is exactly the kind of source drift this document is meant to
prevent.

Pre-launch identity checks, all required:

1. Source worktree is detached at the frozen SHA, and
   `git status --porcelain` is empty for product files.
2. `core.runtime_identity.capture_runtime_identity().source_id` equals the
   source ID reported by the running backend's health identity.
3. `identity.database` resolves to the scratch world's run `atom.db`, never
   `backend/data/atom.db`.
4. `identity.cwd` is the world's `backend_root`.
5. The frontend returns an ATOM health identity and its compiled API origin is
   the scratch backend port, not `:8001`.

Recommended capture worktree (outside the preparation worktree):

```bash
git worktree add --detach /private/tmp/atom-browser-17b80d0de 17b80d0de
cd /private/tmp/atom-browser-17b80d0de
test "$(git rev-parse HEAD)" = 17b80d0deecedbb18fa21c59e5c27dad53c2174a
```

---

## 2. Boundaries, labels and non-claims

Allowed in the scratch capture:

- Real backend public routes (`/api/agents/*`, `/api/boards/*`, `/api/auth/*`).
- Real `GenericAgent`, task lifecycle, durable `AgentJob`, `AgentExecution`,
  `HITLAction`, the registered `tasks.create` action, and its default oracle
  read-back.
- Real frontend built from the frozen source, driven by Playwright against an
  isolated world.
- Existing provider-shim mechanism for the **provider response only**.
- Restarting the scratch backend and frontend while the durable job is waiting.

Not allowed / not claimed:

- No live provider, live model, account, credential, send, spend, download,
  deploy or connected-system write.
- The shimmed ReAct steps are **simulated high-level reasoning**. They prove UI,
  transport, durable wait/resume, authority and effect verification. They do
  **not** prove served-model quality, model choice or prompt quality.
- The scripted responses are authored provider completions, not manufactured
  final outcomes. Routing, execution, persistence, oracle verification and
  result projection must still run in production code.
- No new production feature flag, no new mock engine, no hand-authored final
  plan, no DB-written "completed" job, no job-row patch.
- Success must not be claimed from HTTP status, toast text, model prose or the
  UI badge alone.

The existing repo precedent for this split is
`backend/tests/test_agent_generic_information_wait.py`: real routes, real
lifecycle/registry, real `tasks.create` and default oracle; only the model
transport is doubled and explicitly labelled. The same rule applies here, but
through the browser and a live scratch server.

---

## 3. Existing harness to compose (do not rebuild)

Use these existing pieces:

| Piece | Role |
|---|---|
| `backend/scripts/orchestration_acceptance/run_isolated.py` | World export, storage guard, per-run DB seeding, sandbox/launch. Use `--snapshot-working-tree` from the frozen worktree. |
| `backend/scripts/orchestration_acceptance/provider_shim.py` + `run_isolated.launch_shim()` | Existing loopback OpenAI-compatible provider substitute. Serves authored completions and records calls; no network and no real key. |
| `backend/scripts/orchestration_acceptance/case5_browser_recovery.py` | Closest existing end-to-end precedent: isolated world + shim + real frontend copy + Playwright + durable DB checks. Reuse its launch shape, not its chat-specific scenario. |
| `backend/scripts/orchestration_acceptance/browser_verify.py` (`ui_login`) | Real login-form driver. Prefer it over token/cookie seeding. |
| `backend/scripts/orchestration_acceptance/preview_stack.py` | Not suitable for this case: it launches the unmodified app and therefore needs a real provider. Do not use it for a no-live-model capture. |
| `scripts/acceptance/employee_g5_ui_durable_wait.py` | Two-phase state-file/restart pattern only; do not reuse its model calls. |

There is no existing single driver for this exact Agents-page scenario. The
bounded preparation is therefore a thin scratch runner that **imports and
composes** the existing modules above. It must live in the scratch harness
(world/evidence directory or `scripts/acceptance/`), not in production code.

### Scripted sequence (simulated high-level reasoning)

Author four steps, selected from the durable execution history/context so a
restart can resume correctly rather than restarting at step 1:

1. **First wait** — `information_wait`: question
   `What title should the closing task have?`, missing fact `task title`,
   subject `closing task`.
2. **Second wait** — after the first answer is present, `information_wait`:
   question `What priority should the closing task have?`, missing fact
   `priority`, subject `closing task`.
3. **Registered effect** — after the second answer is present, `actions`:
   `tasks.create` with the real scratch `board_id`, `column_id`, the first
   answer as `title`, and the second answer as `priority`.
4. **Final answer** — after the tool result is present, a final answer such as
   `Created the closing task from both authorized facts.`

Selection must use discriminators that appear only in the resumed prompt, e.g.
`AUTHORIZED INFORMATION ANSWER` plus the prior answer/history, not a
process-global pop counter. This is what makes the restart honest. The shim
capture must show one provider call per reasoning step and no polling while
waiting.

Fallback if the existing shim's text completion is not accepted by the real
structured consumer: use the existing process-test pattern from
`test_agent_generic_information_wait.py` — a scratch launcher that imports the
app after installing the `LLMService.generate_structured` transport double,
then serves it. Keep that double inside the scratch harness, label it
`transport-only / simulated high-level reasoning`, and do not change production
code or add a runtime flag. The provider-shim route is preferred because it is
already an established acceptance mechanism.

---

## 4. Dependency inventory (verified at preparation time, no installs)

Use the existing acceptance interpreter, not the preparation worktree:

- `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` — Python 3.14.7,
  `playwright 1.58.0`, `pytest 9.1.1`, `httpx 0.28.1`, `requests`, `sqlalchemy`,
  `docx`, `uvicorn`, `fastapi`.
- `backend/venv314` is **not** present in the preparation worktree; the capture
  worktree must either be root's existing acceptance worktree or symlink
  `backend/venv314` to the existing interpreter. Do not install.
- Playwright's bundled Chromium cache is absent for both interpreters. Use the
  installed browser explicitly: `chromium.launch(headless=True,
  channel="chrome")` → `/Applications/Google Chrome.app`. Do not run
  `playwright install`.
- Node.js `v25.2.1` x64 is available at `/usr/local/bin/node`.
- `frontend-nextjs/node_modules` already resolves to an installed tree
  (Next 16.2.2). Reuse it; **no `npm install` and no dependency update**.
- The real frontend must run from a directory copy/symlink farm that excludes
  `.env.local` and the user's `.next`; use `case5_browser_recovery.start_frontend_copy`
  or the equivalent. Do not start a second Next dev server in the user's
  `frontend-nextjs` tree.

Disk budget: use the existing `storage_policy` refusal before any build. At
preparation time the workspace had roughly 2.3 GB free. A scratch world with a
code export, small fixture DB, one run directory and a frontend copy fits the
stated 300–800 MB envelope; do not build if the guard refuses.

---

## 5. Preflight — every item must pass before launch

Run from the frozen worktree's `backend/`:

```bash
/Users/rushiparikh/projects/atom/backend/venv314/bin/python -m core.world_storage_guard check
```

Requirements:

- Guard reports OK. **Never** set `ATOM_WORLD_STORAGE_BYPASS`.
- World root is the configured `data/acceptance_worlds`; never a missing or
  dangling path.
- `python -m scripts.orchestration_acceptance.storage_policy space ...` (or the
  launcher's own `_check_disk_before_world`) has enough headroom.
- Ports chosen for backend, frontend and shim are free. Refuse a stale listener;
  never attribute an old process's answer to this run.
- No request may reach `:8001`, `:3000`, or any user dev/server origin.
- `backend/data/atom.db` and the live BYOK files are never opened by the
  harness; the shim uses a placeholder local key only.
- Confirm the world's admin password source before login:
  `<world>/backend_root/logs/bootstrap_admin_password.txt` (mode 0600) or the
  scratch `ADMIN_PASSWORD` set at world creation. The password is read into
  memory only and never printed, logged or screenshotted.

Build only if the world is absent and the checks above pass:

```bash
/Users/rushiparikh/projects/atom/backend/venv314/bin/python \
  scripts/orchestration_acceptance/run_isolated.py \
  --name browser_wait_17b80d0de \
  --snapshot-working-tree --refreeze-db --rebuild-world
```

`--snapshot-working-tree` is mandatory so the export is the frozen working
tree. If an older world already exists with a different MANIFEST, do not reuse
it silently; re-resolve or rebuild explicitly.

---

## 6. Scenario — ordinary login to verified same-job result

Use one browser context for the whole positive scenario so the per-user job
locator and cookies survive reload/restart. Use a fresh scratch world.

### Step 0 — prepare the real board and enabled GenericAgent through public routes

The scripted `tasks.create` needs a real board and column, and the scratch world
starts with no employee agent. Create both through public product routes as the
scratch admin (in-memory token only; do not write the token to evidence):

```text
POST /api/agents/custom   {"name": "Wait Acceptance Employee",
                           "description": "Scratch employee for information wait",
                           "category": "acceptance"}
POST /api/agents/{agent_id}/promote
POST /api/boards          {"name": "Browser wait acceptance",
                           "seed_default_columns": true}
GET  /api/boards/{board_id} → first column id
```

The promote call is scratch setup so the post-answer `tasks.create` runs as the
registered action instead of entering the separate maturity approval gate. It
does not grant the information answer any effect authority; the answer remains
a fact and any governed effect approval would still be separate. Do not insert
`AgentRegistry`, `Board`, `BoardColumn`, `BoardTask`, `AgentJob` or `HITLAction`
rows directly.

### Step 1 — ordinary login

- Navigate to `{frontend}/login`.
- Fill `[data-testid="login-email-input"]` with `admin@example.com`.
- Fill `[data-testid="login-password-input"]` with the scratch password.
- Click `[data-testid="login-submit-button"]`.
- Wait for the URL to leave `/login` (real auth path, not token/cookie seeding).
- Capture only the landing URL and a screenshot with the password field masked.

### Step 2 — enabled Agents page Run objective

- Navigate to `/agents`.
- Wait for the agent list and choose an enabled card:
  `[data-testid="agent-card-<agent name>"]` whose
  `[data-testid="agent-status-badge"]` is not Paused/Stopped.
- Click the card's `Run` button.
- In the Run dialog fill the objective textarea with a bounded objective, e.g.
  `Create a closing task after asking me for its exact title and priority.`
- Click `Run Agent`.
- Capture the `POST /api/agents/{agent_id}/run` request/response with the
  `job_id` and `execution_id`; do not capture the Authorization header.

### Step 3 — first missing-information question

The Agents page must show `AgentJobWaitPanel` for the admitted job:

- `[data-testid="agent-job-status"]` = `Waiting for your answer`.
- `[data-testid="agent-job-question"]` contains the exact first question.
- `[data-testid="agent-job-blocking"]` names the missing fact.
- The panel says this is information, not action approval.
- There is **no** `agent-job-completed` and no result.
- Read back `GET /api/agents/{agent_id}/jobs/{job_id}` and record:
  `agent_id`, `job_id`, `execution_id`, `wait.id`, `wait.correlation_id`,
  `wait.question`, `wait.missing_fact`, `job_status`, `next_action`.
- Assert the GET is a pure read: job status and `wait.id` are unchanged after
  the read. The shim capture must show no extra provider call.
- Assert the provider prompt/system instruction did not receive the
  `correlation_id` or `hitl_action_id`; the model may see the question and
  missing fact, but not the server-owned wait authority.

Screenshot: `01_first_question.png`.

### Step 4 — restart while waiting (real backend + frontend)

Before answering, stop both the scratch backend and the scratch frontend
(process groups), verify both ports are free, then relaunch:

- Backend: `run_isolated.launch_server(..., reuse_run_dir=<same run dir>,
  provider_shim=True, shim_port=<same shim>)`.
- Frontend: restart the same directory copy against the same backend port.
- Recreate the shim only if it was stopped; keep the same script hash and
  board/column IDs.
- Verify the new `/health` identity: new pid, same source ID, same DB path,
  same cwd. Verify the frontend health and compiled API origin again.

Reload `/agents` in the same browser context. Assert:

- The same `job_id` locator is restored from the per-user cache.
- `GET /api/agents/{agent_id}/jobs/{job_id}` returns the **same** `execution_id`,
  the **same** `wait.id`, the **same** `correlation_id`, and the **same** first
  question.
- The UI shows the question again; the typed answer is empty; no completion.

Screenshot: `02_after_restart_same_wait.png`.

### Step 5 — answer the first question (exact same job)

- Type the first answer (e.g. `Quarterly close checklist`) into
  `[data-testid="agent-job-answer-input"]`.
- Click `[data-testid="agent-job-answer-submit"]` once.
- Capture the `POST /api/agents/{agent_id}/jobs/{job_id}/answer` body/response
  with `Authorization` redacted.

Assert:

- Response is `202` (second wait) or an authoritative continuation state.
- The response's `job_id` and `execution_id` equal the original ones.
- `job_status` is still `waiting`; the new `wait.id` and
  `wait.correlation_id` differ from the first; the second question is the
  priority question.
- The typed answer field is cleared because the wait identity changed.
- No `agent-job-completed`; exactly one POST was sent (double-click control is
  covered separately).
- Durable `HITLAction` count for this job is now 2; the first row is approved
  with the submitted answer, the second is pending.

Screenshot: `03_second_question.png`.

### Step 6 — reload/readback the same job and second question

- Perform a real `page.reload()` on `/agents` (not a re-render).
- Assert the panel rehydrates the **same** `job_id`/`execution_id`, the same
  second `wait.id`/`correlation_id`, the same second question, and an empty
  answer input.
- Assert the page did not create a new job or dispatch a provider call during
  reload; the shim capture count is unchanged.

Screenshot: `04_reload_same_second_question.png`.

### Step 7 — answer the second question and verify the real result

- Type the second answer (e.g. `high`), click Send once.
- Assert the final response is a durable success:
  - `job_status == "success"`, `outcome == "success"`.
  - `execution_id` is the same execution as every prior step.
  - `result.output` is the expected final answer.
  - `result.steps` contains a `tasks.create` step with
    `oracle_verified == true`.
- Assert the UI shows `agent-job-completed` and the public result; no failure
  banner and no approval prompt.
- Read back `GET /api/agents/{agent_id}/jobs/{job_id}` and assert the same
  success/result, not just the POST envelope.
- Read the scratch DB read-only and assert:
  - exactly one `AgentJob` row for this job, status success;
  - exactly one `AgentExecution` row for this execution, status success;
  - exactly two `agent_information_request` `HITLAction` rows, both approved;
  - exactly one `BoardTask` row on the scratch board, with the expected title
    and priority;
  - no extra job/execution/task rows from the reload or duplicate clicks.

Screenshot: `05_verified_result.png`.

Rows/counts, IDs and the source health identity go into the evidence JSON. No
token, cookie, header or credential value is written.

---

## 7. Negative controls (bounded, after the positive)

Run these against the same scratch world where possible. Keep them finite and
record the exact response.

1. **Duplicate answer** (after the positive job is successful) — replay the
   first answer with the same `correlation_id`. Expect idempotent
   `already_resumed` or `409`; assert exactly the same single `BoardTask`,
   same execution and no new provider call.
2. **Stale answer reuse** (while a second question is open) — execute this
   between Step 5 and Step 7 of the positive timeline, before the second answer,
   so the second wait is still pending: POST the first wait's `correlation_id`
   with the first answer. Expect `409`; the second wait remains pending, the job
   remains waiting, no `BoardTask` is created and no provider call is made. Then
   continue the positive path with the second wait's own correlation. If the
   runner needs the positive path to stay pristine, run this on a second bounded
   job that reaches two waits instead. Also assert the UI's 409 path refreshes
   authoritative state and does not auto-resend.
3. **Cancelled job** (separate bounded job) — start a second job, let it reach
   an information wait, cancel/stop it through the product's authorized stop
   path, and verify from the durable job read that the job is durably cancelled
   before answering. Then answer the old correlation. Expect `409`; the job
   stays cancelled, no result is shown as success, no `BoardTask` is created and
   no provider call revives it. If the stop route does not produce a durable
   cancelled job in this scenario, record that as a finding; do not patch the
   row to make the negative pass.
4. **No success from HTTP 200** — explicitly assert that none of the above
   negatives is treated as completion by the UI or evidence script; only durable
   `job_status=success` plus the oracle/DB read-back satisfies the positive.

Do not reuse a success-shaped response for a negative. Preserve the actual
response bytes and status in the evidence.

---

## 8. Evidence bundle (redacted, hash-manifested)

Write into a scratch evidence directory outside the repo source, e.g.
`<world>/evidence/browser_wait_<sha10>/`:

```text
source.json          git rev, dirty state, runtime source_id, frontend build id
stack.json           pids, ports, world/db/cwd, health identity, frontend origin,
                     shim port/script sha256
scenario.json        ordered steps, checks, pass/fail, exact timings
capture/*.jsonl      allowlisted request/response fields (no auth/cookies/tokens)
screenshots/*.png    login, first question, after restart, second question,
                     reload, final result
shim_capture.jsonl   existing provider-shim capture (request counts, served head)
durable.json         row counts + the single job/execution/task/waits records
MANIFEST.json        sha256 of every evidence file + source commit
```

Request/response capture is allowlisted: method, path, status, `agent_id`,
`job_id`, `execution_id`, `wait.id`, `correlation_id`, `job_status`, `outcome`,
`reason`, `next_action`, `result.output`, `steps[].action.tool`,
`steps[].output.oracle_verified` and `steps[].output.task_id`. Redact
`Authorization`, `Cookie`, `Set-Cookie`, any `*token*` field, `SECRET_KEY` and
BYOK paths. Never include browser localStorage contents.

The manifest must be generated after all files are written and must match the
bytes on disk. Do not commit credentials, live DB rows or unredacted captures.

---

## 9. Abort and teardown

Stop and preserve evidence if any of these occur:

- world storage guard or disk-space check refuses;
- source SHA/runtime source ID mismatch;
- a live-origin request appears in the browser network log;
- the same wait cannot be re-read after restart;
- a wait is answered by a different correlation or by a second job;
- the final result lacks `oracle_verified` or the durable row is missing;
- any HTTP 200 is the only evidence of success.

Teardown in a `finally` block: stop the frontend, backend and shim process
groups; confirm ports are free; never kill unrelated user processes. Leave the
world and evidence intact for root review; clean only this run's reproducible
scratch artifacts after the evidence manifest is written.

---

## 10. Exact command inventory (root runs; this document does not)

```bash
# 0. frozen source
git worktree add --detach /private/tmp/atom-browser-17b80d0de 17b80d0de
cd /private/tmp/atom-browser-17b80d0de
git rev-parse HEAD   # must be 17b80d0deecedbb18fa21c59e5c27dad53c2174a

# 1. interpreter and dependencies (existing; do not install)
PY=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
$PY -c "import playwright, pytest, httpx, requests, sqlalchemy, docx"

# 2. storage guard before any write
cd backend
$PY -m core.world_storage_guard check

# 3. world (only if absent, and only after the guard passes)
$PY scripts/orchestration_acceptance/run_isolated.py \
  --name browser_wait_17b80d0de \
  --snapshot-working-tree --refreeze-db --rebuild-world

# 4. scratch runner (thin composition of the existing modules)
#    uses run_isolated.launch_shim + launch_server(provider_shim=True),
#    case5_browser_recovery.start_frontend_copy,
#    browser_verify.ui_login, and Playwright channel="chrome".
$PY scripts/acceptance/browser_agent_job_wait.py \
  --world browser_wait_17b80d0de \
  --backend-port 8031 --frontend-port 3131 --shim-port 8097 \
  --out <scratch-evidence>/browser_wait_17b80d0de

# 5. restart while waiting (the runner does this itself; manual equivalent)
#    stop process groups, verify ports free, then:
#    launch_server(..., provider_shim=True, reuse_run_dir=<same run dir>)
#    restart the same frontend copy against the same backend port

# 6. evidence integrity
$PY -c "import json,hashlib,pathlib; ..."   # write/verify MANIFEST.json
```

If the scratch runner does not yet exist, create it only inside the scratch
harness and only from the existing modules above. It must not change production
code, add a feature flag, install packages, or call a live provider.

---

## 11. What root must confirm before capture

- [ ] Capture worktree is exactly the frozen SHA (or a named successor).
- [ ] Guard/disk checks passed; no bypass used.
- [ ] Scratch world DB/cwd are under `acceptance_worlds`, not live `data/`.
- [ ] Backend and frontend are the frozen source, not the preparation branch.
- [ ] Shim is loopback-only and contains no real credential.
- [ ] Login is the real form, not token/cookie seeding.
- [ ] Both waits are re-read from the authorized GET after restart/reload.
- [ ] Final success is `job_status=success` + `tasks.create oracle_verified` +
      one durable `BoardTask` row, not a 200 or model sentence.
- [ ] Duplicate, stale and cancelled answers are refused without new effects.
- [ ] Evidence contains IDs/counts/screenshots and no tokens or credentials.
- [ ] This document's preparation scope is preserved; no product fixture work
      was repeated.
