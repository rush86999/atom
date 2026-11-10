# Web Agents creation UI — test results

Browser custom Hire executed product: `708d4d6a5`  
Receipt-binding repair: `31a82b316`  
Current-main merge / fresh-gate head: `7301110ac`  
Base: `38dae97a6f9a1e00179a9ac879c14215b9983d1f`; current main
`230231f5114612f4b31a602190c318667e94f2f1`

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


## Receipt-binding failure-first and after-gate

Root's real-module probe (unchanged, retained as the negative) found the
previous helper accepted a wrong operation/audit receipt, a missing receipt,
and a verified receipt with `effect:none`. Failure-first Jest twins
(`receipt-binding-failure-first.log`) show **13 failed** before the repair.

After the repair, at committed source `31a82b316`:

```
./node_modules/.bin/jest \
  lib/__tests__/agent-creation-retry.test.ts \
  --runInBand --no-coverage --ci --watchAll=false
```

Result: **25 passed** (`receipt-binding-at-31a82b316.log`). The suite covers
guided and custom invalid receipts, the real shared interceptor with exactly
one POST, exact verified and `already_applied` twins, and internally generated
operation ids. The full focused suite: **132 passed**
(`receipt-binding-at-31a82b316.log` group / `fresh-7301110ac-focused.log`);
`tsc`: **0 errors**.

Exact-receipt gate (`receipt_binding_after_gate.cjs`): **14/14**, 0 failing at
`31a82b316` and again at `7301110ac`. It requires the exact backend-shaped
nested `verification.audit_id`; all invalid cases reject, actual verified and
`already_applied` pass. The old minimal 4-case fixture is not used as the pass
gate because its valid twin omits that nested audit.

## Root independent gate

Root independently re-ran the actual helper and receipt boundary at
`31a82b316`:

- `/private/tmp/brennan-brief/CREATION_UI_RECEIPT_BINDING_ROOT_AFTER_31a82b316.json`:
  **5/5** counterprobes (wrong operation, missing receipt, contradictory
  effect reject; backend-shaped valid and replay pass).
- `/private/tmp/brennan-brief/CREATION_UI31_ROOT_JEST_GATE.json`: **51 passed
  across 5 suites, 0 failed**; helper Git match true; helper SHA256
  `ecfbd44a475e089bcdd8416f9ff60a5660dc6f3b9db6f85bc7584d0ebfad8f8c`.
- Raw `gate.log` retained.

Copies are in `root-independent-31a82b316/`.

## Fresh merged-head gates

Current main `230231f51` is the squashed guided integration with the same tree
as base `38dae97a6`. It was merged as `7301110ac`; the merged product tree is
exactly the tested `31a82b316` tree. Fresh at `7301110ac`:

- focused frontend: **132 passed** (`fresh-7301110ac-focused.log`);
- `tsc --noEmit`: **0 errors** (`fresh-7301110ac-tsc.log`);
- exact-receipt gate: **14/14**, 0 failing (`fresh-7301110ac-gate.log`).

No full browser campaign was repeated for these source-identical gates. The
browser join remains the `708d4d6a5` capture with its explicitly preserved raw
health limits in `SOURCE_IDENTITY_RECONCILIATION.md`.

## Boundaries

No backend, qualification, API client, store or review-engine change; no live
model/provider/DB/credentials/send/spend/deploy/dependency. Existing
qualification controls remain on the untouched base. No PR merge or
self-acceptance.
