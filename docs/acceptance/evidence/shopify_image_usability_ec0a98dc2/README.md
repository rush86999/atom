# Shopify image usability repair — bounded evidence

**Status:** controlled-transport runtime/tests only. No live provider, CDN/image
download, model, browser, server, account, key, spend, send or install was used.
Only the Shopify Admin HTTP and provider asset HTTP leaves are doubled. Root
capture and fulfillment/next-family worktrees were not touched.

**Base:** `197f054c8`. **Prior image receipt (withheld):** `6a89cf5d5`.
**Root usability negative:** `fc5aff150` / root log (3 failed, 11 passed).
**Runtime/test repair:** `ec0a98dc2`.

## Root failure and repair

Root's permanent `backend/tests/test_lead_asset_usable_image.py` showed that
empty bytes, HTML and a signature-only truncated PNG were certified
`verified=True` when the MIME label and digest/size matched. That was
header/hash-only proof, not usable image proof.

`core/asset_content_receipt.py` now:

- fully decodes supported **static** images with Pillow: `Image.open` probe,
  `verify`, reopen and `load`;
- rejects empty, HTML, truncated/invalid and non-image bytes regardless of MIME
  or digest;
- requires decoded format to match the declared MIME (`PNG`/`JPEG`/`WEBP`/`GIF`
  aliases normalized; mismatch refused);
- bounds dimensions **before** full decode at 40,000,000 pixels and treats
  Pillow decompression-bomb warnings/errors as refusals;
- refuses animated/unsupported formats rather than claiming first-frame
  usability;
- records decoded format/width/height in the existing read-receipt fields and
  evidence.

`core/shopify_mutations.py` binds decoded width/height to the provider by-id
image metadata, while all accepted image qualifiers remain compared. A
mismatched provider dimension or qualifier is unverified.

## Fixtures and controls

- Positive fixtures are deterministic, actually encoded 320x240 PNGs matching
  the provider fixture metadata.
- The provider-transform negative now uses a **different valid PNG**, so it
  proves exact digest mismatch rather than incidental decoder refusal.
- Real JPEG support is exercised.
- MIME/format mismatch, pixel bound, empty/HTML/truncated/non-image, wrong
  id/product/digest/dimensions/qualifiers, missing readback, six-image/no-count
  cap, replay and provider-transform outcomes are covered.
- SSRF controls remain: allowlisted hosts, DNS pinning, private/loopback
  refusal, no redirects, no credentials/cookies, identity encoding, bounded
  bytes.
- **Raw URL-only images remain OPEN and unverified.** This is not normal URL
  ingestion or transformation equivalence.

## Tests and exact source

- `usability.log`: **33 passed** (`test_lead_asset_usable_image.py`,
  `test_asset_content_receipt.py`, `test_lead_shopify_image_content_receipt.py`).
- `product_contract.log`: **57 passed**.
- `article_contract.log`: **55 passed**.
- `compile-pyflakes.log`: production compile/pyflakes clean.

Commands:

```bash
cd /private/tmp/atom-shopify-image-content-receipt-20261107/backend
PY=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
SCRATCH=$(mktemp -d); mkdir -p "$SCRATCH"/{data,office,lancedb}
TESTING=1 DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" ATOM_OFFICE_DIR="$SCRATCH/office" \
LANCEDB_URI="$SCRATCH/lancedb" \
$PY -m pytest tests/test_lead_asset_usable_image.py \
  tests/test_asset_content_receipt.py \
  tests/test_lead_shopify_image_content_receipt.py -q
# 33 passed
```

## Honest limits

- Pillow static formats only; animated/unsupported formats fail closed.
- No live Shopify/CDN metadata or byte behavior is claimed; a real readback is
  still required to confirm the base CDN URL preserves bytes or intentionally
  transforms them.
- 40 megapixel is a documented proof-read bound, not a product API image-count
  cap.
- Raw URL-only ingestion and provider transformation equivalence remain OPEN.
- Shared modules changed: `core/asset_content_receipt.py`,
  `core/shopify_mutations.py`, `integrations/shopify_service.py`,
  `core/oracle/postcondition_verifiers.py`. Agent2 fulfillment must
  rebase/review its separate worktree. Root acceptance remains withheld.
