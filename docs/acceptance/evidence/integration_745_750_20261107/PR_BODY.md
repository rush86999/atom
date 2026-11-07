# Integrate frozen reviewed PRs 745 / 748 / 749 / 750 (+ docs 747)

One normal integration branch from current `origin/main` `36fa4ce39`.

## Frozen heads

- 745 `182dab986cce9fcd5afb587ddd3451c1532ca524`
- 748 `e0ca9cca0d5627e39d6eaa7cdafac8d0d0905d41`
- 749 `3a188840dbf92a1f8f0ceb5eb1471051d44ed991`
- 750 `bf94fc1f81732375055130e1ccc8e4fed8586d0c`
- 747 docs-only `ee6b3efd8ee23f1387d4c0ff768d7652e657c5a6`

All merges are normal. No force, rebase or history rewrite. Every parent and
prior evidence packet is preserved.

## Conflict resolution

- CI test list is a union: zero union paths missing, four intentional additions
  (image controls + fulfillment action caller). No drops/skips/xfail.
- Oracle postcondition file keeps both complete registration blocks:
  radio projector/matcher/verifier and fulfillment
  projector/matcher/verifier.
- Request expectations keep both complete additive material blocks and keys.
- Shopify image helpers and fulfillment helpers are both preserved.
- No duplicate AST function was introduced in reviewed files. Pre-existing
  `action_registry` duplicate functions are unchanged because their decorated
  action metadata differs.

## Identity crosswalk

`IDENTITY_CROSSWALK.json` covers positive maturity, neutral wait/browser,
radio, image, fulfillment, and Article/product originals. No frozen production
or test function is missing. Canonical current-main
`generic_agent`/API identities remain byte-equal.

## Verification

Mandatory bounded heavy-test gate, actual result:

- **784 passed**
- **exit 0**
- executed source `1f1d410ef`

The matrix is the meaningful family union: independent negatives/valid twins,
radio exact readback, image receipt/SSRF/decode, product/Article/blog material
and replay, fulfillment shape/identity/replay, positive maturity, neutral
wait/browser identity, shared Oracle/caller controls.

A prior save-state attempt hit ENOSPC and was not treated as a product failure.
The task was resumed after disk recovery and completed under the gate.

`TESTING=1`, scratch SQLite, scratch basetemp, only provider HTTP leaf doubled.
No live provider/CDN/model/server/browser/account/credential/send/spend/install
action.

Evidence:
`docs/acceptance/evidence/integration_745_750_20261107/`

Root retains independent verification and merge. Old PRs are not closed by this
checkpoint.
