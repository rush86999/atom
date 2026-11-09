# Mobile session recovery — controlled evidence

Runtime source: `ae102ca2d`. This packet qualifies JavaScript session ownership,
not a working native mobile app, keychain restart, or live identity-provider flow.

## Reproduced failures and repairs

- Reload requests lacked stored authorization; the obsolete API cache could
  survive logout, and an old 401 could delete a replacement session. Requests
  now carry exact generation ownership through real Axios interceptor/config
  handling; same-token relogin is a distinct generation.
- Delayed login/refresh could restore owner-logged-out credentials, while logout
  waited on its backend. Existing token/profile keys now have serialized,
  generation-conditional commits and local-first revocation. Native operations
  are not claimed to form a cross-key transaction.
- Invented 24-hour expiry and duplicate refresh dispatch were replaced with
  timezone-qualified server expiry and generation-scoped single-flight refresh.
  Mobile refresh uses the existing device-bound backend route.
- Current revocation and partial-save failures clear mounted provider identity.
  Delayed startup reads cannot restore an old profile or clear a newer login.
  Valid expired-session refresh has an authenticated positive twin.

## Verification

Five decisive negative captures are retained unchanged at their exact source
commits (3, 3, 7, 2, and 2 failing cases respectively). `capture-source-bindings.json`
binds every captured input hash to Git: seven captures, 247 or 249 files each,
zero mismatches, no reconstruction. The final selected regression passes
808/808 across 21 actual files with zero skipped/pending tests. The raw Jest
report, commands, source hashes, exit records and logs are included.

The full strict compiler still fails with 408 diagnostics. No compiler options,
file exclusions or test skips were used to make it appear green. Earlier
intermediate integration runs exposed stale SDK options or account fixtures;
those were corrected to the real storage options and response contracts, without
removing assertions. They are not claimed as product-negative proofs here.

## Remaining product boundaries

Native storage/migration and actual process restart, complete application
bootstrap, live backend authentication, device ownership, WebSocket reconnect,
offline queue account binding and unknown-effect reconciliation remain open.
An in-process revoked flag cannot prove old native bytes are absent after a
restart. No duplicate dispatch or native persistence guarantee is inferred.

No new provider, credential, model download, deployment, real account operation
or OS permission request was used. Accepted web/employee evidence retains its
original identities. A separate final Flash review is in progress; this packet
is not a claim of independent acceptance or completion of the app goal.

## Primary references

- https://axios-http.com/docs/interceptors
- https://docs.expo.dev/versions/latest/sdk/securestore/
- https://react.dev/reference/react/useEffect

Backend mobile login/refresh contracts were inspected from the committed source;
they were not exercised against a live account in these controlled checks.
