# Agent guidance copy follow-up — plain review language and existing CI step

Status: **frozen copy/presentation successor submitted for independent review.**
No merge or self-acceptance, no runtime policy change.

Base/current main: `914b9470d254293369475cd9f0fecdbf76acd650`  
Executed source: `6b1afd370fb6cb9ccd097378128e16b68980ed6a`  
Prior copy evidence: `agent_guidance_copy_1afb29abd` at `1afb29abd/534e33ec6`

## PM-requested polish

The underlying direction (no automatic confidence/clean-run promotion; core
connectors explicitly deferred) is unchanged. This follow-up:

- replaces “scoped qualification review” with plain English: a **review of the
  employee’s actual work for the role**;
- preserves the audited owner-exception contract rather than saying every
  promotion always requires a review:
  - normal promotion needs readiness plus the review;
  - an allowed owner exception is recorded with its reason;
  - domain selectors do not create exemptions;
- keeps AUTONOMOUS as the product goal with domain rules still reviewed;
- adds the three copy/profile/tier regression files to the **existing**
  `Agents release-surface regression tests` frontend step in
  `.github/workflows/ci.yml`; no new job, step name, engine or check name;
- preserves all prior frontend steps and the current-main/CI union;
- does not drop or modify PR838 receipt `retry:false`/receipt checks (they are
  not part of this branch).

No maturity, authority, action-policy, connector-runtime or product-profile
capability changed.

## Verification

| Check | Result |
|---|---|
| Focused copy/profile/tier + Agents page | **54 passed** |
| `tsc --noEmit` | **0 errors** |
| `git diff --check` | clean |
| YAML parse of `.github/workflows/ci.yml` | valid |
| Core profile twin | connector setup explicitly deferred; Data path + hire |
| Full profile twin | connector setup remains, admin Settings hint only |
| Owner exceptions | reason recorded; no domain-selector promise |
| Old claims | no automatic graduation, all-action approval, score-only promotion, or server secret env names |

No browser or graduation/employee campaign was rerun. No live connector,
model, provider, credential, send or spend was used.

## Boundaries

Frontend copy/tests and one existing CI step only. Root owns PR838/main
reconciliation; this branch does not edit the frozen UI branch or its receipt
tests. Root owns integration/final review; no merge.
