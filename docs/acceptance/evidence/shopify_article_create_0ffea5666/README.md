# Shopify article create — registered exact-id/material Oracle

Exact implementation source: `0ffea5666` on
`codex/shopify-article-oracle-20261107`, based on the independently reviewed
blog delivery `d7e8f972b`.

Root product PR `72c73001d` and the root formatter fix `e359b5ac7` (with
prerequisite test commits `4e0ead635`, then `00979657d`) are **not integrated**
on this isolated branch. Their `_normalized_number` lines were not modified, so
they can be applied without overwrite.

## Failure first

The predecessor handler returned the provider's raw response:

```python
article = await ShopifyService().create_article(...)
return {"success": True, "article": article}
```

It retained no exact id, performed no current-store readback, and compared no
authorized field. Under the real Generic mutation consumer the predecessor is
honestly reported as `uncertain`, not verified. `failure-first.log` captures the
missing capability against the reviewed `HEAD^` implementation:
**35 failed, 1 passed, exit 1**. The one passing control is the already-honest
lost-confirmation case.

## Implementation

The new path reuses the existing registry / Generic durable claim / shared
Oracle / domain-neutral receipt projector machinery. No new store, router,
operation engine or provider access was added.

- `core/action_registry.py`: the registered `shopify_create_article` handler
  refuses missing/foreign/moved/inactive/ambiguous stores, body store or
  credential selectors, and a missing blog id/title before transport.
- `core/shopify_mutations.py`: article payload/material projection covering
  every authorized registered field — `blog_id`, `title`, `body_html`,
  `author`, `tags`, `published` — plus the producer, exact id readback and
  durable receipt projector/matcher. Optional/tag inputs are canonicalised
  deterministically; an absent provider field is omitted from observed
  material, never defaulted to the accepted value.
- `integrations/shopify_service.py`: `get_article` by exact blog/id:
  `GET /admin/api/{version}/blogs/{blog_id}/articles/{article_id}.json`
  (https://shopify.dev/docs/api/admin-rest/2026-07/resources/article).
- `core/oracle/postcondition_verifiers.py`: registered independent verifier.
  It requires the frozen operation/request digest, provider receipt, exact
  remote id, same current workspace store, and a fresh exact-id readback in the
  authorized blog whose every authorized field matches. Missing/contradictory
  or unavailable proof stays unverified.
- `core/oracle/request_expectations.py` and `core/connected_actions.py`: freeze
  and bind the same article payload, so a succeeded claim replays only from its
  durable exact id and changed material is refused before readback or resend.

## Controls

`backend/tests/test_oracle_shopify_article_create.py` joins the REAL registered
action, REAL GenericAgent durable claim, REAL ShopifyService methods and REAL
shared Oracle. Only `ShopifyService.http` is doubled. Covered:

- exact create: one POST, two GETs (producer + Oracle), exact id/store/blog and
  every material field;
- pre-effect refusal: missing/foreign/moved/inactive/ambiguous store, body
  store/credential selectors, blank blog id/title;
- wrong returned id; every authorized field individually refuted (`blog_id`,
  `title`, `body_html`, `author`, `tags`, `published`);
- provider omits `published`: explicit unverified row, not green;
- absent/contradictory readback and unidentifiable effect;
- same-operation replay and process-style restart: one POST total,
  `already_applied`;
- changed current material for every field, missing current resource, changed
  store, missing durable identity and unavailable readback:
  `committed_unverified`, no second create;
- changed same-operation material: `conflict` before readback/transport;
- lost confirmation: `uncertain`, never resent;
- failed identity receipt: `uncertain`, never labelled rolled back, never
  re-created.

## Exact runs

`run_and_capture.py` is the executable spec: existing Python 3.14.7
interpreter, `TESTING=1`, explicit synthetic `SECRET_KEY`, fresh scratch SQLite
`DATABASE_URL`, scratch data/Lance/output and blank provider credentials.

- `failure-first.log` / `failure-first-exit.json`: predecessor implementation,
  **exit 1**, 35 failed / 1 passed.
- `focused.log` / `focused-exit.json` / `focused.xml`: current implementation
  across article + blog + product material/replay + Oracle/Generic/service
  suites, **311 passed, 1 deselected, exit 0**.

The deselected node is the real-Alembic upgrade test, which needs the project
venv's `passlib` (absent from this machine's pytest interpreter). The migration
revision-contract node still runs; no migration contract changed.

No live provider/model/browser/server/account/credential/dependency-install/
deployment/dev-database action was made. Only the HTTP leaf is doubled in the
controls. The scratch SQLite database was pruned after log/XML capture;
`run_and_capture.py` recreates it. Root independently reviews and owns
integration/acceptance; this packet is not self-acceptance and does not relabel
the blog or product packets.

## Finite delivery

This completes the already-authorized Shopify article-create write. The
remaining queued Shopify write is fulfillment create; it is not part of this
delivery and was not started here.
