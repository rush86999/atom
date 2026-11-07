# Frozen-PR integration — 745 / 748 / 749 / 750 (+ docs 747)

One normal integration branch from current `origin/main` `36fa4ce39` for the
frozen reviewed submissions:

| PR | Frozen head | Scope |
|---|---|---|
| 745 | `182dab986cce9fcd5afb587ddd3451c1532ca524` | positive maturity / neutral wait / browser identity |
| 748 | `e0ca9cca0d5627e39d6eaa7cdafac8d0d0905d41` | real Shopify image-content receipt and SSRF/decode controls |
| 749 | `3a188840dbf92a1f8f0ceb5eb1471051d44ed991` | radio exact durable send/readback identity |
| 750 | `bf94fc1f81732375055130e1ccc8e4fed8586d0c` | Shopify fulfillment official REST shape / line namespaces |
| 747 | `ee6b3efd8ee23f1387d4c0ff768d7652e657c5a6` | docs-only current completion checkpoint |

Branch: `codex/engineer-integration-20261107`
Executed source: `1f1d410ef39177f00008f20f925a0ebfcdbf135b`

## Merge method

Only normal `git merge` operations were used. No force, rebase or history
rewrite. Every frozen parent and prior evidence packet is preserved.

Conflict resolutions:

- `.github/workflows/ci.yml`: test-list union. No test dropped, skipped,
  deselected or marked xfail.
- `backend/core/oracle/postcondition_verifiers.py`: both complete additive
  blocks retained — radio projector/matcher/verifier and fulfillment
  projector/matcher/verifier.
- `backend/core/oracle/request_expectations.py`: both complete additive blocks
  and both expected-material keys retained.
- `backend/core/shopify_mutations.py` and
  `backend/integrations/shopify_service.py`: image-content helpers and
  fulfillment helpers both preserved by the normal merge.

CI union proof: `CI_UNION.json` records 137 union test paths from current main
plus the four frozen code heads; the integration CI has 141, with **zero
missing** and four intentional additions (the three image controls and the
fulfillment action caller control).

## Identity crosswalk

`IDENTITY_CROSSWALK.json` compares each family's frozen production/test
function identities with the integration tree:

- positive maturity 745;
- neutral wait / browser identity from current main + 745;
- radio 749;
- image 748;
- fulfillment 750;
- Article/product originals from current main.

No family has a missing production or test function. The crosswalk also records
hashes for every compared file.

Canonical current-main identities that were not part of the reviewed changes
remain byte-equal, including:

- `backend/core/generic_agent.py`
- `backend/api/agent_routes.py`
- `backend/api/canvas_pdf_routes.py`

Duplicate AST audit:

- No duplicate top-level function/class identity was introduced in any reviewed
  file.
- The two `_mini_app_db_query` / `_mini_app_db_write` definitions in
  `backend/core/action_registry.py` pre-exist on `origin/main`; their function
  source is byte-identical but their decorated action metadata differs.
  They were not removed, because removing either would change which decorated
  action identity wins and is outside this frozen integration scope.

## Decisive matrix

Run through the mandatory bounded heavy-test gate:

```text
python /private/tmp/atom-agent-cli/run_bounded_test_gate.py \
  --cwd <integration>/backend -- \
  <existingPython> <packet>/run_and_capture.py
```

Actual result:

- **784 passed**
- **exit 0**
- executed source `1f1d410ef`
- `TESTING=1`, fresh scratch SQLite, scratch basetemp
- only provider HTTP leaf doubled
- no live provider/CDN/model/server/browser/account/credential/send/spend/install
  action.

The matrix is the meaningful union of the reviewed families, not a broad
unrelated suite:

- root independent negatives and valid twins;
- radio exact send/readback;
- image content receipt, SSRF/DNS/HTTP safety, real decode and provider
  transform limits;
- Shopify product/Article/blog material and durable replay originals;
- fulfillment official shape, quantity namespaces, status, line identity and
  replay controls;
- positive maturity and neutral wait/browser identity;
- shared Oracle registry/request-expectation/retry controls;
- affected caller controls.

A prior attempt was stopped by **ENOSPC** while saving state. That is recorded
as a disk interruption, not a product failure; no pass was assumed. After
root's byte-exact archive freed space, the same unfinished task was re-run
under the gate with 4.8 GiB free and completed as above.

## Safety

- No live model/provider/CDN/browser/account/credential/send/spend/install/
  deploy action.
- No live or shared database.
- Existing permissions/config (`opencode.jsonc`) is unchanged and contains no
  credentials.
- Root retains review and merge; this packet is evidence, not self-acceptance.

## Finite delivery

This checkpoint integrates all frozen reviewed submissions into one normal
main-based branch, with identity and CI-union proofs and one actual 784-pass
matrix. No old PR was closed or merged.
