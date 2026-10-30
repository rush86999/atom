# Conversation-derived learning — security and full-app successor evidence

Source commit: `eac50600eca46e668ca094e83c84f1f4208e1d88`

This directory supersedes `conversation-learning-59464e7/` for the successor
review. It keeps the accepted local-core tag `local-core-2026-10-30-final`
(`da9cc8b12`) unchanged and does not relabel historical browser/live evidence.

## Boundary fixes

- **Cross-workspace email disclosure:** an empty authorized canvas scope now
  returns no threads, no messages and no resources. Authorization is applied
  to the canvas query before any limit; the resource catalog is workspace-
  scoped too. Default-scope (`NULL`) canvases are visible only to the default
  workspace, never to another workspace.
- **Foreign-employee promotion:** every candidate mutation re-authorizes the
  target employee against the authenticated workspace and tenant. A candidate
  whose employee moved elsewhere is no longer readable or promotable.
- **Reviewer identity:** confirm/promote/reject/resolve/revise derive the
  reviewer from the authenticated database user. Client-supplied
  `reviewer: "owner"` is ignored. A viewer is refused; member+ is required.
- **Stale-lesson reuse:** promotion validates current reference versions, and
  normal `get_agent_lessons` retrieval checks the governing dataset version.
  A changed source blocks reuse even without calling the candidate endpoint;
  the raw journal keeps the old lesson with `stale` and
  `revalidation_required` provenance.
- **Core profile/UI:** the `learning` capability is enabled in the core
  profile and appears in navigation. `/learning` uses an authorized employee
  selector, not a raw employee-id field, and exposes an apply-to-unfamiliar-
  work action after promotion.

## Test results

| Suite | Result |
|---|---|
| Conversation-learning service/routes | **30 passed** |
| Assignment regressions | **126 passed** |
| Teaching/renderer regressions | **137 passed** |
| Frontend targeted (5 suites) | **35 passed** |
| TypeScript `--noEmit` | clean |
| Production frontend build | success |

The permanent negatives include empty-workspace disclosure, foreign-employee
targeting, viewer refusal, forged reviewer text, source change blocking
work-time reuse without manual revalidation, and promotion blocking after a
source change.

## Full-app browser journey

The journey ran against the production frontend build and the full app on
`127.0.0.1:3130` / `127.0.0.1:8071`, using an isolated world:

1. open the persisted local email thread;
2. select the authorized employee from the selector;
3. propose a lesson with a `multiply_sum` method and review the resolved
   `rates.xlsx` binding;
4. confirm and promote;
5. apply the approved method to an unfamiliar row → **15 USD**;
6. change the governing dataset version from `v1` to `v2`;
7. reload: candidate `invalidated`, apply blocked with HTTP 409;
8. restart the backend against the same world;
9. reopen: candidate still `invalidated`, raw lesson `stale` with
   `revalidation_required`, apply still blocked with HTTP 409;
10. no page errors.

Artifacts: `browser-journey-part1.json`, `browser-journey-part2.json`,
`browser-journey-promoted.png`, `browser-journey-stale.png`,
`browser-journey-after-restart.png`, and the two journey scripts.

## Bounds

Only persisted local email-canvas audits are read. No live mailbox access,
token refresh, real send, credential change, source writeback, arbitrary URL
fetch or recursive traversal was performed. Reference detection is
deterministic; candidate creation is explicit. Deployment, publication,
source shutdown and additional real sends remain deferred.
