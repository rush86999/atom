# OAuth renewal check — 2026-10-29

Status: **shared resolver repaired and locally verified; live Microsoft renewal
is blocked by missing client configuration, not by revoked user consent.**

## Actual path traced

1. `integrations/onedrive_journey_routes.py` calls
   `OneDriveService.get_access_token_resolution()`.
2. `OneDriveService.get_access_token_resolution()` calls
   `core/integrations/token_store.py::resolve_integration_token()` with the
   provider aliases `onedrive`, `microsoft`, `outlook`, `microsoft365`.
3. The resolver reads the newest active `IntegrationToken` row, decrypts the
   access token, and refreshes when it is within the two-minute expiry margin.
4. The refresh callback is `OneDriveService._refresh()` (no separate
   refresher was added). It exchanges the refresh token at
   `login.microsoftonline.com/{tenant}/oauth2/v2.0/token`.
5. The resolver persists the new access token and expiry, and now persists a
   replacement refresh token when the provider returns one.

Other consumers of the shared resolver: `box_service` and
`google_drive_service`. Their return contract is unchanged; only the optional
`status_out` diagnostic and replacement-refresh persistence were added.

## Defects found and repaired

### Replacement refresh token was discarded

The resolver persisted only `access_token` and `expires_at`. A provider that
rotates refresh tokens on exchange would leave the old refresh token in the
store; the next restart would then try a consumed token. Now:

- response contains `refresh_token` → encrypt and persist it;
- response omits `refresh_token` → leave the existing token untouched;
- `refresh_token_replaced` records which case occurred;
- no token value is written to logs or status.

### All refresh failures looked like “disconnected”

`OneDriveService._refresh()` swallowed every exception and returned `None`.
The resolver now classifies:

| State | Meaning | Reconnect? | Retry? |
|---|---|---|---|
| `valid` | access token still valid | no | no |
| `refreshed` | ordinary expiry, refresh succeeded | no | no |
| `refresh_unavailable` | no refresh token stored | yes | no |
| `invalid_grant` | consent expired/revoked | yes | no |
| `invalid_client` | client configuration rejected | **no** | no |
| `refresh_rejected` | other provider rejection | no | no |
| `transient` | network/5xx/429 | no | yes |
| `no_grant` | no IntegrationToken row | legacy fallback allowed | no |

A revoked/invalid/transient state no longer falls through to legacy
ConnectionService credentials. Legacy fallback is limited to `no_grant` (no
IntegrationToken grant at all), preserving old installs without masking a
failed current grant.

### Live finding: missing client credentials

The stored Microsoft access token expired at `2026-10-29T00:27:28Z`. The
existing refresh token was presented through the already authorized refresh
flow with the app's own client id; the provider required a client secret:

- provider error: `invalid_client` / `AADSTS7000218`
- live status: `token_state=invalid_client`
- `requires_reconnect=false`
- reason: “Microsoft rejected the refresh client configuration. This is not a
  revoked user grant; restore the configured client credentials.”

`backend/.env` currently has the Microsoft client id/secret entries stripped,
so the runtime cannot complete a live exchange. This is a configuration gap,
not consent revocation. No credential was manually replaced, recreated or
rotated, and no interactive reconnect was demanded.

## Local controls

All controls use scratch storage and fake provider transport; no real token is
printed or persisted in evidence.

| Control | Result |
|---|---|
| Expired access → successful refresh → authorized Graph read | pass |
| Replacement refresh token survives a new resolver session | pass |
| Response without replacement preserves the existing token | pass |
| Revoked/invalid_grant does not fall through to legacy credentials | pass |
| Invalid_client is configuration, not revoked consent | pass |
| Transient/network failure is retryable, not revoked | pass |
| Missing refresh token is `refresh_unavailable` | pass |
| Classification/status strings contain no tokens | pass |

Test files:

- `backend/tests/unit/test_token_store.py`
- `backend/tests/unit/test_token_store_persistence.py`
- `backend/tests/unit/test_onedrive_refresh_classification.py`

## Evidence

- `docs/acceptance/evidence/connected_core_20261028/oauth_live_status.json` —
  live status after expiry; no token values.
- `docs/acceptance/evidence/connected_core_20261028/oauth_renewal_controls.json`
  — local control summary.

## Boundary

Live successful renewal cannot be claimed until the existing Microsoft client
configuration is restored. The code path is verified locally; the live
provider correctly rejects the missing client secret as `invalid_client`.
Changed-source refresh is also blocked by this same configuration gap and by
the need for an authorized disposable source item.
