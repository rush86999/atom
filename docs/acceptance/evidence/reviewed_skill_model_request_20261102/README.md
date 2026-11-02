# Reviewed-skill final model request capture — evidence

Status: **submitted for independent verification; not self-accepted.**

Extends the accepted prompt-consumption evidence with the **exact final model
request** assembled by `GenericAgent._react_step`, plus a precise local-model
serving result. The source includes the other agent's goal-decision CAS commit
`635df02e4` and this test-only request-capture change.

## Executed source

| Item | Value |
|---|---|
| Branch | `codex/brennan-full-app-20261102` |
| Executed source | `4f93f069ece7fce5270fc024e0d39ed63fe01a75` |
| Worktree | `/private/tmp/atom-consolidated-clean` |
| Tree at execution | clean |
| Accepted product base | `c1074f0a9` (prompt lifecycle) |
| Other product commit included | `635df02e4` (goal pending-decision CAS, Agent 2) |
| Added by this slice | `tests/test_reviewed_skill_agent_consumption.py` final-request control |

## Captured request

`final-model-request.json` is written by the real `GenericAgent._react_step`
path with a capturing `generate_structured` transport. It contains the exact
`system_instruction` and `prompt` passed to the LLM layer:

- system instruction length 4,392 chars; prompt 138 chars;
- `repair_outlook_search` and the reviewed instructions are present;
- generated executable code is absent;
- the request was captured, not reconstructed from the retrieval helper.

## Local model serving

The captured request was sent to a separate Ollama on `127.0.0.1:11437` with
`OLLAMA_MODELS=/Users/rushiparikh/.ollama/models-local`. The owner's servers
were untouched. The request timed out/500 after 3–4 minutes while host load
averages were 34–45 (other model runs active); the exact error is recorded in
`local-model-serve-attempt.log` / `final-model-response.json`. No model
behavior, discretionary judgment or planning quality is claimed.

## Controls

| Control | Expected | Result |
|---|---|---|
| `_react_step` final request | reviewed skill in system instruction; code absent | passed |
| Prompt payload capture | exact `system_instruction` + `prompt` written | passed |
| Earlier consumption controls | GenericAgent, workspace block, fresh session, meta-agent, isolation | passed |

Suites: **492 backend passed** (`backend-tests.log`), **5 focused consumption
controls passed** (`consumption-controls.log`), **7 frontend passed**
(`frontend-tests.log`).

## Scope

No live provider call, credential, spend, send or reseed. The local serving
attempt is availability/transport evidence only. Historical 111/123 and prior
accepted sources/bundles are unchanged.
