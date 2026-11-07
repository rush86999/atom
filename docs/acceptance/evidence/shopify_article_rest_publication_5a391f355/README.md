# Shopify Article REST publication readback — bounded repair evidence

**Status:** controlled-transport repair only. No live Shopify/provider/model,
server, browser, download, install or credential was used. Only the Shopify
Article HTTP leaf is doubled; the registered action, real GenericAgent
consumer, Article material mapper, Oracle and durable claim/replay are real.

**Base:** root article integration `1d7b0ec83`.
**Failure-first commit:** `a1ffa57ec` (independent twin only; 2/2 failed).
**Fix:** `5a391f355` (`backend/core/shopify_mutations.py` + test doubles/twins).
**Final test commit:** `7b03d6e61` (closes the two publication mismatch directions).

## Confirmed provider shape

Official Article REST documentation:
<https://shopify.dev/docs/api/admin-rest/latest/resources/article>

- Readbacks carry `published_at` (ISO 8601 timestamp or null).
- `published` is the request/visibility boolean; the default HTTP doubles must
  not synthesize it as the readback proof.
- The current implementation previously accepted only `published`, so the two
  official positive twins were falsely withheld.

## Mapping

| Observed readback | Verified business state |
|---|---|
| `published_at: null` | draft / unpublished (`published=False`) |
| timezone-aware past timestamp | published (`published=True`) |
| future/scheduled timestamp | not published yet; unknown/refuted |
| missing `published_at` | unknown; never default to requested value |
| malformed value | unknown; never default |
| naive timestamp (no timezone) | unknown; never default |
| `published` + `published_at` disagree | contradictory; unknown/refuted |
| `published` only, no `published_at` | unknown (not official readback proof) |
| `published` + `published_at` agree | explicit compatibility confirmed |

The read receipt records the observed publication state/reason. The accepted
material still expresses the caller's requested `published` intent; the
observer derives the comparable state only from `published_at`.

## Tests

- Independent twin `tests/test_lead_shopify_article_rest_shape.py`: **19 passed**
  — official past/null positives, timezone offset, future/scheduled, missing,
  malformed, naive, contradictory, published-only unknown, requested-published/
  null-readback, requested-draft/past-readback, consistent legacy compatibility
  (justified), replay/no second create.
- Existing Article contract `tests/test_oracle_shopify_article_create.py`:
  **36 passed** — default doubles now emit official REST shape; existing
  wrong-id/material/durable/no-resend controls retained.
- Failure-first twin at `a1ffa57ec`: **2 failed** (positive publication and
  draft). Root's original log is preserved as
  `root-article-rest-shape2-negative.log`.

## Exact commands

```bash
cd /private/tmp/atom-shopify-article-rest-shape-20261107/backend
PY=/Users/rushiparikh/projects/atom/backend/venv314/bin/python
SCRATCH=$(mktemp -d)
mkdir -p "$SCRATCH"/{data,office,lancedb}
TESTING=1 \
DATABASE_URL="sqlite:///$SCRATCH/atom.db" \
ATOM_DATA_DIR="$SCRATCH/data" \
ATOM_OFFICE_DIR="$SCRATCH/office" \
LANCEDB_URI="$SCRATCH/lancedb" \
$PY -m pytest tests/test_lead_shopify_article_rest_shape.py -q
# 19 passed

TESTING=1 ... $PY -m pytest tests/test_oracle_shopify_article_create.py -q
# 36 passed
```

`verification.json` records the base/failure/fix commits, mapping and exact
counts.

## Coordination and limits

- **Shared-module behavior change:** `backend/core/shopify_mutations.py`
  `observed_article_material` now derives publication from `published_at`.
  Agent2 fulfillment owns its separate worktree; it must rebase/review this
  shared change before relying on Article publication proof.
- No new engine, store, router, schema or authority was added. The existing
  durable claim/replay path is unchanged; a replay re-reads the current
  readback and stays committed-unverified if publication/material changed.
- REST `latest` article docs were consulted; GraphQL/Media API and live Shopify
  normalization are not covered. Actual provider behavior remains to be
  rechecked independently.
- Root's current capture/worktree is separate and was not touched. Root
  acceptance remains withheld until the independent recheck.
