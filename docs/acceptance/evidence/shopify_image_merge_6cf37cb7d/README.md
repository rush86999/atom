# Current-main merge checkpoint — Shopify image usability

**Status:** controlled-transport checkpoint. No live provider, CDN/image,
model, server, browser, account, credential, spend, send or install was used.
Only Shopify Admin HTTP and provider asset HTTP are doubled. Root capture and
fulfillment/next-family worktrees were not touched.

## Exact source and merge

- Image worktree base: `197f054c8`; prior withheld image receipt: `6a89cf5d5`.
- Root usability negative: `fc5aff150`; root verified image/usability log:
  `root-image-usability-verified.log` (33 passed).
- Image runtime/evidence: `ec0a98dc2` / `3801b0da5`.
- Fetched `origin/main`: `e39e2af2f` (includes PR739 product material/durable
  replay and wait repairs).
- **Merge head:** `6cf37cb7d`; parents `3801b0da5` and `e39e2af2f`.
- Root Article PR746 and Blog741 were **not present** in the fetched
  `origin/main`; the branch retains its existing article/blog changes. No
  duplicate engine or second authority path was introduced.

### Real conflicts and resolution

Conflicts were real and were resolved without rewriting history:

- `backend/core/shopify_mutations.py` (add/add) and
  `backend/core/oracle/postcondition_verifiers.py`: kept the branch's superset.
  Independent function comparison confirmed the current-main product material
  and verifier bodies are present unchanged, with only the image proof added.
- `backend/core/action_registry.py`: kept the branch's stricter single-store
  workspace resolution; main's product action/material code is retained.
- `backend/core/connected_actions.py`, `request_expectations.py`,
  `integrations/shopify_service.py`, `.github/workflows/ci.yml`: kept the
  branch's article/blog/image additions; the main side of those hunks was empty.
- No current-main product fix or original negative was removed.

## Verification on the merge head

- `usability.log`: **33 passed** — root usable-image negatives, real
  PNG/JPEG decode, MIME/format/dimension bindings, SSRF matrix, qualifier and
  replay controls.
- `product.log`: **57 passed** — current-main product material/create/replay.
- `article.log`: **55 passed** — Article REST shape plus existing article
  contract.
- `compile-pyflakes.log`: production compile/pyflakes clean.

Commands (fresh scratch DB per group):

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

## Preserved boundaries

- Real image decode/verify/load; empty, HTML, truncated and non-image bytes
  refused even with matching MIME/digest.
- 40,000,000-pixel pre-decode bound; decompression-bomb and animated/unsupported
  formats fail closed.
- Decoded dimensions/format bound to provider by-id metadata; accepted
  qualifiers preserved and compared.
- Provider-transform remains unknown/unverified; transform fixtures use a real
  valid image to prove digest mismatch.
- Raw URL-only remains **OPEN/unverified**.
- SSRF allowlist, DNS pinning, no redirects, no credentials/cookies, identity
  encoding and byte bounds unchanged.

## Handoff

See `HANDOFF.md` for exact branch/head, source hashes, PR state, and the
remaining independent root acceptance. Agent2 fulfillment owns a separate
worktree and must rebase/review the shared Shopify/Oracle changes.
