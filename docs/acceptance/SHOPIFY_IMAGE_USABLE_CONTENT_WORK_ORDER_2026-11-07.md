# Shopify product-image usable content proof — actionable work order

**Status:** read-only diagnosis. No implementation, no live provider/model,
no image download, no server/browser. Root assigns implementation after review.

**Owner:** Agent2 (shared Shopify product/article lane). This worker must not
edit the shared Shopify files in this slice.

**Remains OPEN:** PR739 / `codex/shopify-product-lead-review-20261107` head
`72c73001d`. The branch's own evidence says: “Provider CDN image rewriting
remains unverified content, not usable image-byte proof.” This work order does
not close PR739 or claim whole-app ORACLE completion.

## Current goal and ownership

- `docs/engineering/APP_COMPLETION_STATE_2026_11_07.md:22` — Agent2 owns exact
  remote-identity replay for the registered Shopify product create; other
  registered creates remain queued; no live provider follows.
- `docs/acceptance/GOAL_COMPLETION_DELTA_2026_11_06.md:291` — direct mutations
  and whole-app ORACLE remain OPEN; the registry-only count is not provider
  acceptance.
- `docs/acceptance/evidence/shopify_product_material_b71aa4a78/README.md`
  (at `72c73001d`) explicitly records the image-content gap.

## Source evidence (re-locate by symbol on drift)

| Area | Source at `72c73001d` | Observation |
|---|---|---|
| Registered parameters | `backend/core/action_registry.py:1760-1774` | `images` is an array of URLs or `{src}` objects; only `title` is required. |
| Action wrapper | `backend/core/action_registry.py:1894-1941` | Resolves the server-owned store, rejects store/credential selectors, then calls `core.shopify_mutations.create_product`. |
| Payload/material | `backend/core/shopify_mutations.py:218-319` | `product_payload` forwards image entries; `accepted_product_material`/`observed_product_material` project every accepted image field. |
| Image comparison | `backend/core/shopify_mutations.py:359-385` | `_image_mismatches` compares every expected key, including `src`; a provider CDN rewrite therefore becomes a mismatch even when the image is correct. |
| Producer/readback | `backend/core/shopify_mutations.py:534-673` | Creates, reads the product by id, builds `read_receipt`, and requires material equality. No image by-id read/content receipt. |
| Shopify service | `backend/integrations/shopify_service.py:31,108-151` | Pinned `API_VERSION = "2026-07"`; `get_product` and `create_product`; no `get_product_image`/content read. |
| Expected material | `backend/core/oracle/request_expectations.py:174-185,283` | Freezes `_oracle_expected_shopify_product` from accepted arguments. |
| Oracle verifier | `backend/core/oracle/postcondition_verifiers.py:41-67,91-209` | Generic receipt/digest/account/verification checks; `_material_fields` has no Shopify image requirement. |
| Existing asset receipts | `backend/core/connected_actions.py:290-294,297-355,573-620,696-782,832-919,2151-2210` | Connected mutations and authorized file/attachment reads already return `read_receipt` with `resource_id`, `account_id`, `coverage`, `access`, `fields`, `evidence`; WorkDrive/OneDrive include `sha256`/`bytes`. |
| Durable claim | `backend/core/outbound_operation_claim.py:123,194,284,398-411` | Durable operation/receipt/replay with `result_json`; Shopify projection lives in `core/shopify_mutations.py`. |
| Existing tests | `backend/tests/test_lead_shopify_authorized_material.py:1-29`; `backend/tests/test_oracle_shopify_product_replay.py` `FakeShopifyTransport._materialize` | The image case uses the same `src` on request and readback; the fake copy never performs a CDN rewrite. The current matrix does not cover the actual gap. |

### Official Shopify docs (fetched 2026-11-07)

- Product: <https://shopify.dev/docs/api/admin-rest/2026-07/resources/product>
  — product `images` is a list of product-image objects (mapped to `media`).
- Product Image: <https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-image>
  — `id`, `position`, `src` (provider-served URL; Liquid filters can return
  modified copies), `width`, `height`, `alt` (returned example), timestamps;
  `product_id`/`variant_ids` are deprecated. **No content hash field.**
- Product Image create: `POST /admin/api/2026-07/products/{product_id}/images.json`
  accepts a `src` that Shopify downloads, or an `attachment` containing image
  data.
- Product Image by-id: `GET /admin/api/2026-07/products/{product_id}/images/{image_id}.json`.
- Product Variant: <https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-variant>
  — price/compare-at decimals remain part of the existing material proof.

## Gap and required proof

A legitimate create can return a different CDN `src` than the caller supplied.
That is not a wrong image. Conversely, accepting a new URL, an ETag, a
`Content-Type`, or a product-level `images` array alone is not image-content
proof. The proof must bind:

1. the image **ID** returned by the create/readback;
2. the by-id image readback (`id`, `position`, `alt`, dimensions);
3. the bytes served at the provider-returned base `src`; and
4. the caller-authorized content expectation (SHA-256/byte count).

Only then may `oracle_verified`/business success be true for the image material.

## Supported parameter boundary (smallest compatible)

Keep the existing `images` array; do not add a new model-visible fetch tool.

Each image entry:

- `src`: required for the URL path; `https` only; no userinfo, fragment, local
  path, `data:`/`file:`/`http:`; no private/loopback/link-local literal. This
  URL is sent to Shopify (which downloads it); Atom must not fetch it.
- `alt`: optional bounded string; compared when supplied.
- `position`: optional unique integer `1..N`; required to certify more than one
  image (array order is not identity).
- `content_sha256`: optional 64-character lowercase hex; the only acceptable
  content expectation. It may come from an existing authorized asset receipt
  (e.g. `brennan.*.read_file` `sha256`) or an explicit caller expectation.
- `bytes`: optional positive integer; compared when supplied.
- `width`/`height`: optional positive integers; compared when supplied.
- `variant_ids`: not supported in this slice (deprecated/provider-owned).
- `attachment`: not supported in this slice; it is a separate base64/authority
  surface, not a reason to claim URL support.
- `id`: never accepted from the caller; read it from Shopify.

Additional bounds: max 5 images, max 8 MiB content per image, bounded timeout.
Proof-only fields (`content_sha256`, `bytes`, `width`, `height`) must be stripped
from `product_payload`; they belong to accepted material, not the provider body.

Raw `src` without `content_sha256` may still create a product for compatibility,
but the result must be explicit `uncertain`/`verification.missing_fields`
(`images.content_sha256`) and must not claim `oracle_verified` or business
success. URL equality alone is never proof.

### Decision requested from root

1. Approve `content_sha256` as the only content expectation for this slice
   (sourced from an existing authorized asset receipt or explicit caller
   expectation).
2. Approve the single new internal read of a **provider-returned** Shopify CDN
   URL under the host/SSRF/byte guards above; no user-visible tool or store
   credential.
3. Confirm whether raw URL-only images should remain `uncertain` after creation
   (recommended, preserves compatibility) or be refused before effect.

## Smallest repo-general implementation

### 1. Provider-neutral asset content receipt

Add a small reusable helper (e.g. `core/asset_content_receipt.py`) or extract
the existing receipt builder; do not create a second proof schema. It must:

- accept only a **provider-returned** asset URL, never the caller's `src`;
- require HTTPS and a host allowlist from a provider registry — for Shopify
  start with `cdn.shopify.com` and `*.shopifycdn.com`; an unknown host is
  `unsupported`, recorded, never fetched;
- call `core.ssrf_guard.validate_url` (existing) and reject private/loopback/
  link-local results;
- use `follow_redirects=False`; refuse any 3xx (or revalidate an allowlisted
  target before following, but refusal is the smaller first step);
- send no Authorization, cookie or provider token to the CDN;
- bound timeout and bytes, require `Content-Type: image/*`, and reject
  HTML/JSON/empty/oversize bodies;
- return the existing receipt fields: `provider`, `operation`, `resource_id`,
  `account_id`, `coverage`, `access`, `fields` (`sha256`, `bytes`,
  `content_type`), `evidence` (host/SHA, no secret), plus the observed
  `width`/`height` when available.

This is a read of the just-created provider resource, not a new user-visible
authority or a general URL fetch.

### 2. Shopify service (Agent2-owned)

- `ShopifyService.get_product_image(token, shop, product_id, image_id)`:
  `GET /admin/api/{API_VERSION}/products/{product_id}/images/{image_id}.json`.
- No new store/token selector. Do not send the Admin token to the CDN.

### 3. Producer/material (Agent2-owned `core/shopify_mutations.py`)

- `product_payload`: forward only provider-supported image fields (`src`,
  `alt`, `position`); strip proof-only fields.
- `accepted_product_material`: retain `content_sha256`/`bytes`/`width`/`height`
  expectations and identity fields; do not use provider `src` as content
  identity.
- `create_product`:
  1. validate/normalize images before dispatch; reject unsafe source URLs;
  2. create, then take image IDs from the create response (or the immediate
     product readback if the create response omits them); missing IDs are
     `missing_fields=["images.id"]`, never success;
  3. read each image by id; require the same `id`, requested `position`, and
     requested `alt`; dimensions must match when authorized;
  4. read the base provider `src` content through the asset receipt helper;
     compare exact SHA-256/bytes (and dimensions);
  5. put per-image proof in `read_receipt.fields["images"]` and set
     `coverage="complete"` only when every requested image passes;
  6. missing/wrong/unsafe/unknown content stays `uncertain` or `mismatch`, with
     `success=False`, no resend, and an explicit reason.
- `_image_mismatches`: compare `id`/`position`/`alt`/dimensions/content receipt,
  not the provider `src`.
- `durable_product_receipt_projection` / `durable_product_material_conflicts`:
  include the image content expectations; replay re-reads the same image IDs
  and content, and a changed material is a conflict before readback.

### 4. Oracle (shared, minimal change)

- `request_expectations` already freezes accepted material; keep the same
  `_oracle_expected_shopify_product` namespace.
- Extend the generic Shopify branch so that when expected images are present,
  `read_receipt.fields.images` must exist and carry the by-id identity plus
  `content_sha256`/`bytes`; otherwise verification is unverified. Do not add a
  Shopify-only success shortcut.

## Decisive controlled HTTP-leaf twins

Double only the Shopify Admin HTTP leaf and the provider CDN HTTP leaf. Keep the
real registered action, real GenericAgent consumer, real producer/material
normalizer, real Oracle, real durable claim/replay and real public routes.

### Valid

1. **CDN rewrite, same bytes** — request `src=https://assets.example.invalid/a.png`
   + `content_sha256=H`; create returns image id `img1`, CDN `src` on
   `cdn.shopify.com`; by-id returns `img1`/position/alt; CDN body hashes to `H`;
   result `applied`, `oracle_verified=True`, one create, one CDN read.
2. **Multiple images** — unique positions/alt; all by-id and content receipts
   present; verified; order is bound by position, not array order.
3. **Replay** — same operation/material replays the same image IDs/SHA without a
   second create; `already_applied`, verified.
4. **Provider-only decorations** — extra CDN query/version or provider fields
   that the caller did not authorize do not create a mismatch.

### Negative / fail-closed

1. Missing image in create/readback, no image ID, or by-id 404 → unverified, no
   success, no second create.
2. By-id returns another image ID/product/shop, or wrong position/alt/width →
   unverified.
3. CDN bytes differ from `content_sha256`, or byte count differs → unverified.
4. CDN returns HTML/JSON/empty/oversized/non-image → unverified.
5. CDN host not allowlisted, private/loopback IP, userinfo, or redirect to a
   non-allowlisted host → refused before any CDN request; zero CDN calls;
   unverified, no success.
6. URL-only input without `content_sha256` → creation may land, but
   `verification.missing_fields` names the missing content proof; no
   `oracle_verified`.
7. Source `src` equals readback `src` but no content digest → still unverified
   (URL equality is not content proof).
8. Changed image/material on replay → `conflict` before readback; no create.
9. Durable receipt absent/old succeeded claim → `committed_unverified`; no
   resend.

Every negative must assert actual `success`/`oracle_verified` is not true and
the durable/product/image rows did not duplicate.

## Expected proof and honest limits

- The new image content path must show `oracle_verified=True` only with
  by-id image identity + exact SHA-256/byte proof; screenshots/HTTP 200/model
  prose are insufficient.
- No live provider, store, token, CDN fetch, image download, browser, server or
  model call is performed in this preparation slice; the tests use controlled
  HTTP leaves only.
- Official contract is REST Admin `2026-07` (the service pin). GraphQL/Media
  API, future versions, and live Shopify normalization are not covered.
- Shopify may apply provider-side image transforms. If the base CDN `src` is
  byte-identical, SHA proof works. If Shopify re-encodes/resizes, the exact
  digest will differ; that must remain `unverified` with a recorded
  `provider_transformed_content` finding, not be weakened to URL/ETag equality.
  A real readback is needed before claiming that the base `src` preserves
  bytes.
- Unknown Shopify CDN hosts are unsupported and recorded; do not broaden the
  allowlist to all of `shopify.com`.
- URL-only inputs without a content expectation cannot be content-certified
  without adding a new source-fetch authority. This work order deliberately
  does not add one; if root wants that path, it requires a separate
  SSRF-reviewed authorized source-asset receipt.
- No implementation of shared Shopify files is authorized by this work order.
  Root reviews and assigns it to Agent2; this document is the deliverable.
