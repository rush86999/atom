# Cutover approval request — `09cccb5b0`

**Requested:** one reversible cutover of the local Atom pilot (`:8001` /
`:3000`) to the `[ingested]` fix candidate, **with the actual unfiltered-BYOK
provider profile disclosed below**.
**Status: NOT APPROVED. No cutover has been executed.**

Clear human authorization naming this candidate and scope is sufficient;
no magic phrase is required.

## What is being approved

| Item | Exact value |
|---|---|
| Product commit | `09cccb5b0b977f86c0a39d59af5b922c83143e7f` |
| Product tree | `4c7ec787c8ff1f81baa89f1cdc3c40496ef44b1f` |
| Launch/runtime commit | `4bfcbc2adc3a6bb36568eef4a000c65910bb795f` (clean) |
| Release tree | `/private/var/folders/sq/kf_272b520nc5wnsp27hq1h00000gn/T/opencode/atom-release-09cccb5b0-20261024` |
| Verification | attempt 9: **59/61 checks true**; all 59 functional workflow checks pass; intended-route parity fails |
| Frontend build | Next 16.2.2 webpack, Node 20.19.6, npm 10.8.2, `BUILD_ID=VHwW5YQ_s140w5s6u7HWl`, API `http://127.0.0.1:8001`, loopback opt-in |
| Interpreter | `/Users/rushiparikh/projects/atom/backend/venv314/bin/python` 3.14.7 |
| Live gate | `6d66d0b8b3b2c9a24efbe111a750c477f623a207d34692dcd4fa07cfceb88dd2` |
| Current pilot | `8c593e57031e` clean, backend `:8001` pid 16055, frontend `:3000` pid 16488 |

## Maintenance window

**2026-10-24 14:30–15:30 EDT / 18:30–19:30 UTC.**

- Do not start after 14:50 EDT.
- If smoke has not passed by 15:25 EDT, roll back.
- One attempt only; a rollback ends it. The request lapses if not started.

## The route finding you are accepting

Attempt 9 copied the pilot's **full 13-key / 37-provider BYOK** into the
isolated world; the live files were read-only. The workflow passed, but the
actual routes were not the attempt-8 Ollama/DeepSeek profile:

| Leg | Actual route |
|---|---|
| L3 reply | `openrouter` / `z-ai/glm-5.3-flash` |
| S3 reply | `opencode-go` / `glm-5.3-flash` |
| S7 reply | `opencode-go` / `glm-5.3-flash` |
| Structured interpretation | `deepseek` / `deepseek-v4-pro` |
| Edit planning | `opencode-go` / `glm-5.3-flash` |
| Tool planning | `opencode-go` / `glm-5.3-flash` |

All POST destinations were configured providers (DeepSeek, local Ollama,
OpenCode Go, OpenRouter); there was no unconfigured/rogue destination. But
OpenCode Go and OpenRouter were outside the intended Ollama/DeepSeek reply
profile. Attempt 8's 60/60 was an artifact of its DeepSeek-only isolated
store and does **not** transfer to this product/configuration.

**Approval means accepting these actual configured-provider routes for the
pilot.** If you require Ollama/DeepSeek parity, do not approve; hold for a
routing-containment change and a new rehearsal.

## Configuration and provider settings

- Existing pilot BYOK is preserved in place: all 13 keys and 37 provider
  definitions remain. No credential is deleted, added, or re-scoped. The
  historical filtered `candidate-byok/` store is not used.
- Additive flags: `ATOM_TURN_INTERPRETATION=1`,
  `ATOM_TURN_INTERPRET_PIN=deepseek:deepseek-v4-pro`,
  `ATOM_TURN_INTERPRET_CAPTURE=1`, `ATOM_TURN_DECISION_ROUTING=1`,
  `ATOM_ASYNC_EDIT_PLAN_MODEL=deepseek/deepseek-v4-pro`,
  `ATOM_PREFERRED_LLM_PROVIDER=ollama`,
  `ATOM_PREFERRED_LLM_MODEL=llama3.1:8b`.
- Preserve `CHAT_FINALIZATION_M1=1`, `CHAT_FINALIZATION_M2=1`,
  `ATOM_TASK_LIFECYCLE_ENABLED=1`,
  `ATOM_STREAM_FALLBACK_RESERVE_SECONDS=70`, and existing origins.
- Stores remain the pilot's absolute SQLite/LanceDB/BYOK paths.
- Intended routes remain Ollama/DeepSeek; actual observed routes are the
  table above. The smoke records actual routes and fails on any destination
  outside the configured set.

## The `[ingested]` fix

The confirmed paragraph-deletion defect is fixed. The boundary now removes
only a positively identified carrier prefix and keeps the source label and
body. Ordinary quotations, marker mentions, explanatory prose, mismatched
markers, and explicit quote requests are preserved. The tradeoff is that
internal metadata in a retained body (e.g. `Owner:` in a fixture excerpt)
can remain visible; no answer-bearing paragraph is deleted. Line-numbered
block removal remains a separate pre-existing path with value/decoy guards.

## Smoke that must pass

1. Fresh quiescent snapshot; start backend on `:8001`; health identity
   `4bfcbc2ad`, `dirty=false`, live DB/BYOK paths.
2. Frontend `/login` 200 and real browser sign-in.
3. Upload a unique smoke record; ask for `CEDAR-42`; require correct answer,
   source filename, persisted history, and recorded actual provider/model.
4. Create a draft; edit `Net 45` → `Net 30`; exactly one write, other fields
   preserved.
5. Identical re-ask; zero additional writes, body unchanged.
6. Reload history/canvas; restart the backend once; same identity and
   persisted answer/body.
7. Record every outbound provider POST. Allowed: DeepSeek, local Ollama,
   OpenCode Go, OpenRouter. Any other destination fails.
8. `post_smoke_db_fingerprint.json`: user-visible delta equals smoke
   fixtures; background agent rows attributable in logs.

Artifacts under
`docs/acceptance/release_evidence_20261024/cutover_execution_09cccb5b0/`:
`pre_cutover/`, `candidate_health.json`, logs, `browser_signin.png`,
`smoke_sourced_*`, `smoke_edit_*`, `smoke_reask_*`, `provider_posts.json`,
`post_restart_*`, `post_smoke_db_fingerprint.json`, `cutover_summary.json`
(and `rollback/` if needed).

## Rollback conditions

Any of:

- health non-200, wrong revision/dirty state, or wrong live DB/BYOK path;
- frontend login/browser sign-in failure not fixed in 5 minutes;
- sourced answer missing `CEDAR-42`, wrong source, provider failure, or any
  POST to an unconfigured provider after two bounded attempts;
- edit writes zero or more than one time, or changes another field;
- re-ask writes again or changes the body;
- restart loses history/canvas or changes identity;
- DB integrity failure or unexplained user-visible row delta;
- owner aborts.

Rollback stops only candidate PIDs, restores the fresh snapshot and the
four unchanged BYOK/env files, restarts the old backend/frontend, verifies
`8c593e57031e` + `/login` 200, and preserves evidence. No retry in the
same window.

## Approval line (clear authorization is sufficient)

```
I approve the one-attempt cutover of product 09cccb5b0 / launch 4bfcbc2ad
in the 2026-10-24 14:30-15:30 EDT window, accepting the actual
OpenCode Go/OpenRouter GLM-5.3 Flash routes and the smoke/rollback terms.
```

Any reply that does not clearly name this candidate and scope leaves the
hold in force.
