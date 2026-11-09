# Retained commands and scope

Working directory: frontend-nextjs at31ffe48ee, Node20.20.2. Every command was
serialized through the owned disk-gated runner; no provider inference in tests.

```sh
node node_modules/jest/bin/jest.js \
 tests/auth/signin-logout-return-contract.test.tsx \
 tests/components/sidebar-logout-contract.test.tsx \
 components/layout/__tests__/Sidebar.gating.test.tsx \
 components/layout/__tests__/layout.test.tsx \
 tests/lib/backend-credentials.test.ts \
 tests/lib/backend-signin-identity.test.ts \
 tests/lib/backend-session-logout.test.ts \
 tests/pages/api/__tests__/auth-nextauth.test.ts \
 tests/pages/api/__tests__/auth-nextauth-callbacks.test.ts \
 tests/pages/__tests__/login.test.tsx tests/auth/test-signin.test.tsx \
 --runInBand --watch=false --watchman=false --no-coverage \
 --json --outputFile=/private/tmp/root-logout-31ffe48ee-jest.json
node node_modules/typescript/bin/tsc --noEmit
```

Original Sidebar three-case and sign-in-return three-case negatives were run
on a75dd85e0 consumer bytes with the new tests staged only in the owned worktree.
The old role-file baseline used its original seven tests and unchanged parent
Sidebar bytes:6 failed/1 passed. That temporary parent file was restored to the
owned candidate before any candidate gate or browser launch. No test was skipped
or deleted. Raw logs remain private; the assertion report is derived from the
retained successful Jest JSON without console capture.

Browser: normal main backend and frontend on18151/18152; the published ASGI
wrapper delays only /api/auth/logout by30seconds. Optional legacy frontend
PostgreSQL is deliberately unavailable on18153, preventing live DB access.
Captured SMTP only, disabled schedulers, fresh scratch SQLite, no model inference.
Source was clean before startup; generated Next type/build changes explain the
subsequently captured dirty health identity. No app source was changed while
the episode served. Both owned processes stopped before cache cleanup.
