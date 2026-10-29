# Live-connected assignment gate

`preflight.json` is the presence-only Microsoft configuration check taken
before this slice. It records `configured=false` and the two missing client
keys. No live guided start, changed-source refresh, replacement catalog row or
replacement grant was run.

The stored grant is not treated as revoked. The blocker is an administrator
configuration repair plus the exact disposable-source authorization described
in `docs/acceptance/CHANGED_SOURCE_REFRESH_PROTOCOL.md`.
