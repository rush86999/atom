# Agent guidance copy — test results

Executed source: `1afb29abd32e52b22f2d524cdfb22d1bac018ac3`  
Base/current main: `230231f5114612f4b31a602190c318667e94f2f1`

Node 20 with existing frontend `node_modules` linked; no new dependency.

## Focused copy/profile/tier twins

```
./node_modules/.bin/jest \
  components/Agents/__tests__/AgentLaunchGuide.test.tsx \
  components/Agents/__tests__/GuidedAgentCreator.test.tsx \
  components/Agents/__tests__/EmployeeOnboardingGuide.test.tsx \
  --runInBand --no-coverage --ci --watchAll=false
```

Result: **19 passed**.

Covered:

- onboarding guide requires readiness + scoped qualification review and actual
  work; no automatic-promotion claim;
- STUDENT described as read-only; no “approval for every action”;
- creator success says promotion is not automatic and a review is required;
- full profile keeps connector setup and shows workspace-admin Settings
  guidance, with no `*_CLIENT_ID`/`*_CLIENT_SECRET` text;
- core profile explicitly marks connector setup as deferred, offers Data
  upload, and hides the guide after the role employee exists without waiting
  for unavailable connectors.

## Including Agents page

```
./node_modules/.bin/jest \
  components/Agents/__tests__/AgentLaunchGuide.test.tsx \
  components/Agents/__tests__/GuidedAgentCreator.test.tsx \
  components/Agents/__tests__/EmployeeOnboardingGuide.test.tsx \
  tests/pages/agents-index.test.tsx \
  --runInBand --no-coverage --ci --watchAll=false
```

Result: **54 passed** (`focused-at-1afb29abd.log`).

## Type check

```
./node_modules/.bin/tsc --noEmit
```

Result: **0 errors** (`tsc-at-1afb29abd.log`).

## Boundaries

No maturity/authority/action-policy/connector runtime change. No
graduation/employee/browser campaign rerun, no live DB/model/provider/
credential/send/spend, no merge.
