# Controlled same-origin SSO backend and import-order repair

Frozen tested source: `100ac3d99e457a667099bc9cf768a126cada8100`. SSO implementation is `e6e4b387d`; the successor repairs the shared classifier import wrapper without changing provider policy or SSO route bytes.

The new web login/callback/exchange uses existing OAuthState and the canonical backend User, exact configured origin, PKCE S256, a short-lived browser-bound one-use handoff code, and a conditional current-authority claim. Its callback carries no bearer in its URL or HTML. The exchange returns the ordinary bearer as JSON after the claim. The legacy direct-backend HTML callback remains compatibility behavior and is not the new web flow.

Root independently ran 123 tests with normal repository conftest and 10 additional public-router/peer-transaction probes. Both exits were zero. The first normal attempt at predecessor e6 failed in shared classifier import order before SSO fixture setup. The small importlib lookup repair preserves real-module class monkeypatching and provides no fallback classifier. Four broader provider-fixture failures retain identical identities before/after; verification.json discloses them without counting them as passing coverage.

The two independent probe files dynamically reuse the frozen repository test fixtures and real controlled issuer. They are not a new provider or authentication engine. Tests require Python3.11, installed dependencies, TESTING=1, unique scratch DATABASE_URL/data, the compatibility plugin where shown, and the existing bounded gate. Raw logs, generated keys, cookies, tokens and databases remain private. command.json records executed arguments; authentication traces are not published.

This packet does not qualify the frontend callback page or ordinary SSO browser journey, a live identity provider, browser production TLS, PostgreSQL concurrency or soak. Original login/recovery browser episodes remain bound to their actual sources. No model, provider, credential, send/spend or deployment action was used.

Primary references: https://www.rfc-editor.org/rfc/rfc9700/ and https://next-auth.js.org/providers/credentials .
