# Agent guidance copy — reviewed promotion, not automatic graduation

Status: **frozen copy/presentation candidate submitted for independent review.**
No merge or self-acceptance.

Base/current main: `230231f5114612f4b31a602190c318667e94f2f1`  
Executed source: `1afb29abd32e52b22f2d524cdfb22d1bac018ac3`

## Observed gap

The ordinary Agents-page guide said:

- “Every clean run builds confidence; employees graduate Student → Intern →
  Supervised → Autonomous automatically as they earn trust.”
- “Student employees need approval for every action.”
- “Finish training with a performance score to promote them.”

The guided-creator success dialog also implied regular use alone moved an agent
through Intern/Supervised/Autonomous. Connector rows exposed
`ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET`-style server environment names to an
ordinary employee.

These claims do not match the current policy:

- `docs/agents/graduation.md`: experience readiness is necessary but not
  sufficient; scoped capability qualification of actual task/output work by a
  current authorized reviewer is mandatory unless the current owner policy
  explicitly exempts the tier/agent.
- `docs/agents/TRAINING_AND_GRADUATION.md`: an AUTONOMOUS label is not
  unlimited authority; data/action/budget/HITL boundaries still apply, and
  domain exceptions may require review.
- `backend/core/product_profile.py`: the core release enables agents and Data
  but defers the `connectors` capability; broad connector setup is not part of
  that release. `/settings` remains an enabled surface.

## Copy/presentation repair

`EmployeeOnboardingGuide.tsx`:

- clean runs build experience/readiness, but do not promote by themselves;
- promotion also needs readiness requirements plus a current scoped
  qualification review of actual work;
- domain rules can still require human review;
- STUDENT is described as read-only instead of “approval for every action”;
- Interns draft/propose; Supervised handle routine work under the current
  action policy, with high-risk/domain review retained;
- memory copy says “company data you make available,” not only synced
  integration data.

`GuidedAgentCreator.tsx` success state:

- regular use builds experience; promotion is not automatic;
- readiness plus a current scoped qualification review must both be satisfied;
- Intern/Supervised/Autonomous capabilities described without promising
  automatic promotion;
- AUTONOMOUS is the product goal, with domain exceptions still reviewed.

`AgentLaunchGuide.tsx`:

- unconfigured providers now say the provider is not enabled for the workspace
  and direct the user to ask a workspace admin in Settings; no
  `*_CLIENT_ID`/`*_CLIENT_SECRET` names;
- core profile (`connectors` disabled) explicitly says connector setup is not
  part of this release, offers supported Data upload as the next action, and
  does not wait on unavailable connector connections to finish the guide;
- full profile keeps connector setup and sync actions;
- train step says readiness plus a scoped qualification review are required;
  a score alone does not promote.

No maturity, authority, action-policy, connector-runtime or product-profile
capability was changed.

## Verification

| Check | Result |
|---|---|
| Focused copy/profile/tier twins | **19 passed** (guide/creator/onboarding) |
| Focused suite including Agents page | **54 passed** |
| `tsc --noEmit` | **0 errors** |
| Core profile | connector setup explicitly deferred; hire + Data path remain |
| Full profile | connector setup remains; admin-facing hint only |
| Old claims removed | automatic graduation, all-action approval, score-only promotion, env-var names |

No graduation/employee/browser campaign was rerun; no live connector, model,
provider, credential, send or spend was used.

## Boundaries

Frontend copy/tests/evidence only. No backend policy or runtime change. Root
owns integration and final review; no merge.
