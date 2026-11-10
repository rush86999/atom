# GOAL-11 email draft shared-writer repair — actor-claim successor

Source main: `0d5132c2e060a5f2ac338bca143c5e138e607658`.
Baseline audit: `84e0a6362453e865fb63aab8e251867460977338`.
Predecessor repair: `8167d919e9e247b24d9fef6507f8f653011b084e`.
Successor repair: `7625389eb874b2ffe804d24f0f5eb6fa0a15fd93`.

The successor is a requirement-reuse/fidelity correction, not scope
expansion. It replaces the bespoke create actor UPDATE with the established
`tools.canvas_crud_tool.claim_canvas_actor(db, actor)` and freezes the raw
actor once through existing `active_canvas_actor` after `populate_existing`.
Personal NULL scope is normalized separately only for displayed Canvas/audit
scope; the claim compares the raw snapshot (NULL distinct from default/empty).

## Successor change

- Removed the bespoke `_claim_create_actor` conditional SQL.
- `_resolve_actor_scope` now:
  - refreshes the identity map with `populate_existing`,
  - uses existing `active_canvas_actor` for the frozen raw actor,
  - rejects missing/unreadable/inactive principal,
  - requires supplied tenant/workspace to agree with the normalized
    authoritative scope,
  - returns the raw actor snapshot for the shared claim.
- Create calls existing `claim_canvas_actor` in the same transaction before
  Canvas+audit. A peer NULL->default/empty, move or deactivate before the
  claim yields zero effects.
- No new actor engine/state/cache, no production mock escape.
- Added NULL->default/empty raw-move zero-effect twins, active Personal default
  create + ordinary generic PUT edit, scope disagreement/unknown-user refusal.
- 8167 remains the predecessor (root projection PASS 2/4.21s); root will
  parity/retest only the changed actor-claim boundary.

## Gates

| Gate | Result | Log |
|---|---|---|
| New shared-writer suite | 16 passed | `gates/shared_writer_16.proof` |
| Affected email/PDF/attachment/supersession group | 139 passed | `gates/affected_email_139.proof` |
| Legacy route-shape file | 10 passed, 9 pre-existing fixture failures | `gates/legacy_route_9_pre_existing.proof` |

The 9 legacy route failures are the pre-existing message/categorize mock
fixture path (base 0d5132c2e had 13 including save); they remain disclosed,
not skipped. Attachment/review/send controls pass.

## Preservation / non-claims

- Predecessor packets 8167d91 and baseline 84e0a636 remain unchanged.
- Root-owned `backend/api/canvas_routes.py` and
  `backend/core/assignment_executor.py` untouched.
- No CI YAML/goal-index/PR/merge/live DB/provider/model/browser/send/new deps.
- API/component scope, not browser or whole-GOAL-11 acceptance.
