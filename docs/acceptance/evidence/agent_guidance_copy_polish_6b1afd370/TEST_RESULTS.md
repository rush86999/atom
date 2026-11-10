# Agent guidance copy follow-up — test results

Executed source: `6b1afd370fb6cb9ccd097378128e16b68980ed6a`  
Base/current main: `914b9470d254293369475cd9f0fecdbf76acd650`

Node 20 with existing linked frontend `node_modules`; no new dependency.

## Focused copy/profile/tier + Agents page

```
./node_modules/.bin/jest \
  components/Agents/__tests__/AgentLaunchGuide.test.tsx \
  components/Agents/__tests__/GuidedAgentCreator.test.tsx \
  components/Agents/__tests__/EmployeeOnboardingGuide.test.tsx \
  tests/pages/agents-index.test.tsx \
  --runInBand --no-coverage --ci --watchAll=false
```

Result: **54 passed** (`focused-at-6b1afd370.log`).

The assertions now require plain “review of the employee’s actual work for the
role”, owner-exception wording with a recorded reason, no domain-selector
promise, no automatic-graduation/all-action-approval/score-only-promotion
claims, core connector deferral, and full-profile admin Settings guidance.

## Type check

```
./node_modules/.bin/tsc --noEmit
```

Result: **0 errors** (`tsc-at-6b1afd370.log`).

## CI placement

`.github/workflows/ci.yml` existing step:

```
- name: Agents release-surface regression tests
  run: npx jest tests/pages/agents-index.test.tsx \
    components/Agents/__tests__/AgentLaunchGuide.test.tsx \
    components/Agents/__tests__/EmployeeOnboardingGuide.test.tsx \
    components/Agents/__tests__/GuidedAgentCreator.test.tsx \
    --runInBand --no-coverage
```

No new job, step name, engine or check. `git diff --check` clean; YAML parses.

## Boundaries

No runtime policy or product-profile change; no browser/graduation campaign
rerun; no live connector/model/DB; no PR merge.
