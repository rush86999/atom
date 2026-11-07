# Shopify image-content receipt sub-contract — bounded repair evidence

**Status:** controlled-transport implementation only. No live Shopify,
provider, CDN/image, model, server, browser, account, key, spend, install or
deployment call was made. Only the Shopify Admin HTTP leaf and the provider
asset HTTP leaf are doubled. Root's capture/worktree was not touched.

**Base:** repaired article source `197f054c8`.
**Failure-first commit:** `ebc36df9c` (3 valid/replay product twins failed).
**Runtime/test commit:** `5571ecf26`.

## Scope

This closes only the **eligible image-content receipt sub-contract**:

- the caller supplies an explicit content SHA-256/byte count, or an existing
  authorized asset-read receipt with `access=granted`, `coverage=single|complete`,
  provider/resource/account identity, `fields.sha256`/size, and matching
  evidence; supplied explicit and receipt values must agree;
- the producer binds that expectation to the exact provider-created image id
  and product from the readback, re-reads the image by id, verifies the exact
  product/store/image identity and every accepted image qualifier, then reads
  the provider-returned base CDN URL;
- exact SHA-256 and byte count must match. A provider transform remains
  `content_mismatch_or_provider_transform` and is **not** certified;
- the Oracle repeats the by-id/content proof independently on replay; a changed
  or missing current image stays `committed_unverified` with no resend.

**Raw URL-only images remain OPEN and unverified.** This is not full normal URL
ingestion and does not claim transformation equivalence. No source URL is
fetched by Atom; only the provider-returned allowlisted CDN URL is read.

## Implementation and reuse

- New `backend/core/asset_content_receipt.py`:
  - bounded HTTPS only; no userinfo/fragment/non-443 port;
  - explicit CDN host allowlist (`cdn.shopify.com`, `*.shopifycdn.com`);
  - resolves once, rejects any private/loopback/link-local/reserved address,
    pins the chosen public IP while preserving Host/TLS SNI;
  - no redirects, no Authorization/Cookie/token headers, identity encoding,
    image-only content type, bounded bytes;
  - reuses `core.ssrf_guard` and the existing egress host matcher, and returns
    the existing authorized-read `read_receipt` shape.
- `backend/core/shopify_mutations.py`:
  - proof-only fields (`content_sha256`, `bytes`, `asset_receipt`) are retained
    in accepted/durable material but stripped from the provider payload;
  - all other image qualifiers are preserved and compared (`src` only as URL
    identity when no content proof, plus `alt`, `position`, `variant_ids`, etc.);
  - `verify_product_image_content` performs by-id metadata/content proof;
  - durable material conflicts include the content expectation.
- `backend/integrations/shopify_service.py`: `get_product_image` by-id read.
- `backend/core/oracle/postcondition_verifiers.py`: product verifier repeats
  image by-id/content proof.

No new store, router, operation engine, schema, or authority gate was added.
The 8 MiB bound is a proof-read bound, not a global product API image-count cap;
a six-image test confirms no arbitrary count narrowing.

## Tests and exact source

- `image_receipt.log`: **25 passed** — product content valid/raw/wrong/missing,
  by-id wrong id/product, qualifier mismatches, six images, explicit and
  existing-receipt proofs, replay/no second create, provider-transform refusal,
  plus the bounded asset security matrix (private DNS, non-allowlisted host,
  redirect, HTML/JSON/non-image, oversize, exact digest, transform unknown,
  pinned DNS, no credential headers/cookies).
- `product_contract.log`: **57 passed** — existing product material/create/replay
  controls remain green.
- `article_contract.log`: **55 passed** — repaired Article REST publication
  controls remain green.
- `compile-pyflakes.log`: production compile/pyflakes clean.

Commands (fresh scratch DB per group):

```bash
cd /private/tmp/atom-shopify-image-content-receipt-20261107/backend
PY=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
SCRATCH=$(mktemp -d); mkdir -p "$SCRATCH"/{data,office,lancedb}
TESTING=1 DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" ATOM_OFFICE_DIR="$SCRATCH/office" \
LANCEDB_URI="$SCRATCH/lancedb" \
$PY -m pytest tests/test_lead_shopify_image_content_receipt.py \
  tests/test_asset_content_receipt.py -q
# 25 passed
```

## Official contract and honest limits

Official REST 2026-07 resources:
<https://shopify.dev/docs/api/admin-rest/2026-07/resources/product-image>
and <https://shopify.dev/docs/api/admin-rest/2026-07/resources/product>.
The product-image resource exposes `id`, `position`, `src`, `width`, `height`,
`alt`, etc., but **no content hash**; the by-id endpoint is
`GET /products/{product_id}/images/{image_id}.json`.

No live provider/CDN behavior is claimed. The allowlist currently covers the
documented Shopify CDN hosts; unknown hosts fail closed. Any provider byte
transform remains unverified. GraphQL/Media and future API versions are out of
scope. Raw URL-only ingestion remains a separate OPEN row.

## Shared-file coordination

Agent2 fulfillment owns a separate worktree. Shared modules changed here:
`core/shopify_mutations.py`, `integrations/shopify_service.py`, and
`core/oracle/postcondition_verifiers.py`; `core/asset_content_receipt.py` is a
new reusable helper. Agent2 must rebase/review these before integration.
Root acceptance remains withheld pending independent recheck.
