# Web Agents creation UI — test results

Executed source: `708d4d6a5`  
Base: `38dae97a6f9a1e00179a9ac879c14215b9983d1f`

Node20 (`v20.19.6`); existing frontend `node_modules` linked from the task
worktree (no copy). Jest/RTL with the real `lib/api.ts` interceptor for the
counterprobe; no browser or live provider/DB.

## Failure-first: real shared interceptor + creation helpers

```
./node_modules/.bin/jest lib/__tests__/agent-creation-retry.test.ts \
  --runInBand --no-coverage --ci --watchAll=false
```

Before the repair (`failure-first-interceptor.log`): **2 failed**.

- guided create after a 503 confirmation loss: **4 POST attempts**
- onboarding custom Hire after a 503: **4 POST attempts**

After (`interceptor-integrity.log`): **8 passed**, including exactly one POST,
`retry:false`, operation id propagation, 2xx `success:false`, missing agent
id, non-verified verification, pending 202, and custom verified/malformed
responses.

## Focused frontend suite

```
./node_modules/.bin/jest \
  lib/__tests__/agent-creation-retry.test.ts \
  lib/__tests__/api-interceptors.test.ts \
  components/Agents/__tests__/AgentLaunchGuide.test.tsx \
  components/Agents/__tests__/GuidedAgentCreator.test.tsx \
  components/canvas/__tests__/AgentAttachModal.test.tsx \
  tests/pages/agents-index.test.tsx \
  tests/pages/agents-creation-join.test.tsx \
  --runInBand --no-coverage --ci --watchAll=false
```

Result: **115 passed** (`focused-after.log`).

The creation→reload page join (`page-join.log`) confirms the exact returned
`agent_id` appears once in the authoritative list after a verified guided
create and the component passes the operation id.

## Type check

```
./node_modules/.bin/tsc --noEmit
```

Result: **0 errors** (`tsc.log`).

## Changed controls

- no automatic POST after uncertain/503/lost confirmation;
- stable operation id reused only for an explicit unchanged-intent retry;
- pending 202 creates/attaches nothing;
- 2xx success false/malformed/wrong target is not verified;
- exact agent id used for authoritative list/attach;
- STUDENT/no promotion/no scheduler duplicate preserved.

## Boundaries

No backend, qualification, API client, store or review-engine change; no live
model/provider/DB/credentials/send/spend/deploy/dependency. Existing
qualification controls remain on the untouched base `38dae97a6`.
