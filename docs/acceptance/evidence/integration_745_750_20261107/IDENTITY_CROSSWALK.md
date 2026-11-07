# Identity crosswalk — frozen families to integration

Executed source: `1f1d410ef39177f00008f20f925a0ebfcdbf135b`

| Family | Frozen source | Production files | Test files | Missing production functions | Missing test functions |
|---|---|---|---|---|---|
| positive_745 | `182dab986` | 1 | 1 | 0 | 0 |
| wait_browser_main | `origin/main` | 0 | 3 | 0 | 0 |
| radio_749 | `3a188840d` | 4 | 3 | 0 | 0 |
| image_748 | `e0ca9cca0` | 4 | 3 | 0 | 0 |
| fulfillment_750 | `bf94fc1f8` | 6 | 3 | 0 | 0 |
| article_product_main | `origin/main` | 3 | 7 | 0 | 0 |

## Canonical current-main identity

- `backend/core/generic_agent.py`: equal
- `backend/api/agent_routes.py`: equal
- `backend/api/canvas_pdf_routes.py`: equal

## Duplicate AST audit

New duplicates in reviewed files: none.

Pre-existing `action_registry` duplicates:
`_mini_app_db_query`, `_mini_app_db_write`. Their function source is
byte-identical, but their decorated action metadata differs. They are retained
unchanged because removing either would change which decorated action identity
wins and is outside the frozen integration families.

## Registration completeness

- `radio.send_message`: postcondition 1, durable projector 1, durable matcher 1
- `shopify_create_fulfillment`: postcondition 1, durable projector 1, durable matcher 1
- request expectation keys: radio 1, fulfillment 1

Detailed per-file frozen/integration function lists and SHA-256 hashes are in
`IDENTITY_CROSSWALK.json`.
