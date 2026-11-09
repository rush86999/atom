# Explicit persistent web authentication configuration

Executed clean source: `ecba0afe2`. Seven pure-stdlib actual setup tests, 43 installed-NextAuth controls, 180 frontend controls, TypeScript exit 0 and shell syntax pass. Setup tests use temporary files only; no installed/live settings were changed. SDK transport is doubled except the owned loopback deadline test. No browser, model/provider or full-app qualification follows.

The existing quickstart now calls the persistent web setup helper. It preserves configured signing keys and unrelated values, creates private random credentials once, refuses duplicate managed entries and symlink/non-owned file inputs, serializes setup, and uses atomic replacement plus file/directory sync. Local explicit backend settings are generated only when missing. Runtime authentication requires a web secret and valid explicitly configured HTTP(S) backend; private server settings take precedence. Runtime getters avoid embedding the signing key at build time. Legacy public placeholders refuse; no public development default or invented localhost authority remains.

Configured Go DeepSeek Flash performed one bounded public-code read-only review. Duplicate-key rotation, file handling, directory durability, URL normalization and server setting precedence findings were addressed; regression twins added. Private input records were never sent. Existing browser bearer transport is unchanged; live OAuth remains unqualified.

This is a clean-history successor of draft PR802 following GitGuardian incident39877034 in a synthetic backend-test token log. The superseded branch/incident remain intact; no history rewrite, waiver, real credential rotation or force push. That packet's retained log is explicitly sanitized and rehashed. Original runtime/evidence identities are preserved. This packet's clean-source checks were actually rerun after reconstruction.

Next active item is the real public HTTP cookie/logout/restart bridge. Full 18-row app goal map and historical claim denominator remain intact. Web first, mobile last.
