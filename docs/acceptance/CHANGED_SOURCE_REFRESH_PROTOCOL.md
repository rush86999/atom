# Changed-source refresh protocol — disposable workbook

Status: **awaiting owner-provided disposable item and restored Microsoft
refresh configuration.** The historical `Consolidated Price List 2019.xlsx`
will not be modified.

## Predeclared fields

| Field | Value |
|---|---|
| Source item id/path | TBD — owner-provided OneDrive disposable workbook |
| Original version/hash | TBD from the first product sync |
| Original expected result | TBD, frozen before the change |
| One changed input | TBD (single cell or small bounded range) |
| Expected new result | TBD, frozen before the change |
| Records/artifacts expected stale | Assessment results and artifacts bound to the pre-change canvas revision |
| Owner action | Change the workbook manually; agent remains read-only |
| Agent write authorization | None for the source; local canvas/artifact writes only |

## Checks to run after access is restored

1. Product-sync the original disposable workbook; record item id, content
   hash/version, materialized sheet coverage, formula sidecar and a
   deterministic calculation plus a small certified assessment.
2. Freeze the original result, changed input and expected new result here
   before the owner edits the workbook.
3. Owner changes the one input manually. Agent does not write to the provider.
4. Run the existing product sync again. Verify:
   - upstream version/hash changed;
   - new materialized values and formula dependencies are coherent;
   - old version is no longer selected as current;
   - affected assessment reuse is invalidated (canvas revision/rebind
     receipt);
   - prior source/evidence history remains attributable;
   - fresh calculation and assessment use the new version;
   - restart retains the new binding;
   - export/reopen/download agrees.
5. Record failures and limitations; do not retry substantive failures until
   green.
6. Do not touch the production price list, request general writeback, rotate
   credentials, send email or deploy.

## Current blocker

The runtime has no Microsoft client id/secret configured, so the existing
refresh token exchange is rejected as `invalid_client` (configuration), not
`invalid_grant` (revoked consent). Local renewal controls pass. The owner must
restore the existing Microsoft client configuration/reconnect before a live
product sync can run. No secret should be sent through chat or committed.
