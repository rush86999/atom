# Registry-only inventory at `af97665c7`

`inventory.json` was regenerated with the existing
`scripts/acceptance/oracle_mutation_surface_inventory.py --registry-only` at the
code/test commit, with `TESTING=1` and a scratch SQLite URL.

Result: 90 registered actions, 26 declared mutations, **21 covered**, **5
explicitly uncovered**:

- `mini_app_run` (guest execution, out of this packet)
- `shopify_create_article`, `shopify_create_blog`,
  `shopify_create_fulfillment`, `shopify_create_product`

Local mutations: 16 total, 15 covered (only `mini_app_run` uncovered). Zero
undeclared actions; `goals.decompose` remains the one plan-output validator.

`registry_only=true` intentionally skips HTTP route and provider-write scans;
their zero counts are omitted-by-mode, not an absence claim.
