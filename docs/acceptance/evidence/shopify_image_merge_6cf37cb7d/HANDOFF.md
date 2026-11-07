# Private handoff — image usability + current-main merge

- Branch: `codex/shopify-image-content-receipt-20261107`
- Merge head: `6cf37cb7d53e39bc60e11cefe6a4683c06f0cb16`
- Merge parents: `3801b0da5` (image usability/evidence) and `e39e2af2f`
  (`origin/main` PR739 + wait repairs)
- Base image source: `197f054c8`
- Prior withheld image receipt: `6a89cf5d5`
- Root usability negative: `fc5aff150`; verified log:
  `root-image-usability-verified.log` (33 passed)
- Remote/main at fetch: `e39e2af2f`

Tests at merge head: 33 usability, 57 product, 55 article = **145 passed**.
Raw URL-only remains OPEN; provider transforms remain unknown/unverified.

Shared files changed: `core/asset_content_receipt.py`,
`core/shopify_mutations.py`, `integrations/shopify_service.py`,
`core/oracle/postcondition_verifiers.py` (plus article/blog surfaces already
present on this branch). Agent2 fulfillment must rebase/review in its own
worktree. No new store/router/operation engine/schema/authority gate.

Root owns independent acceptance. No live calls were made from this worktree.
