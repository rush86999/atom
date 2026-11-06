# Checkpoint supplement — fresh-browser account-return/session-recovery (2026-11-06)

Follow-through ordered by the lead after screenshot verification. Adds the checkpoint
records behind the already-submitted manifest narrative. **No browser journey was
rerun**: every record below is (a) transcribed verbatim from the run-session captures,
(b) a retained response/log file, or (c) a fresh read-only readback of the retained
frozen scratch DB — labeled per file.

## Files

| File | Content | Provenance |
|---|---|---|
| `checkpoint_identity_auth_me.json` | `/api/auth/me` status + user/workspace identity + onboarding status in phase0 (prerequisite), phase1 (fresh-context re-login), phase2 (expired-session re-login) | transcribed from session captures |
| `checkpoint_row_counts.json` | user/workspace/tenant/user_workspaces counts at three in-run checkpoints + frozen retained-DB readback with row excerpts | transcribed + frozen readback |
| `checkpoint_session_recovery.json` | fresh-state emptiness record, fresh-context 401, expired-token 401s (hash + claims), 10-sample timed no-loop table, seam description | transcribed + retained files |
| `retained_api_responses/me_expired_bearer_401.json` | `{"detail":"Could not validate credentials"}` (43 bytes) | retained response file from the run |
| `retained_api_responses/me_expired_cookie_401.json` | same body, cookie transport | retained response file from the run |
| Appendix (bottom of this file) | 152 sanitized access-log lines: register 422→200, logout 200, login, `/api/auth/me` 401/200, onboarding status/update, health — embedded verbatim because `*.txt`/`*.log` are blanket-gitignored in this repo | filtered from retained backend.log |

## Disclosures

1. **Screenshots 04 and 06 share one sha256** (`96b1b7cc…`): both episodes end on the
   same `/login?callbackUrl=…` render. They are visual-state evidence for two separate
   episodes, not two independent proofs. The decisive records are in
   `checkpoint_session_recovery.json`.
2. **Freshness seam wording**: cleared all cookies + localStorage + sessionStorage via
   page JS, closed the tab, opened a new tab, verified emptiness, then visited the
   protected route. **No separate browser profile was created**; records now say so.
3. **Deep-link callbackUrl finding is source-diagnosed only.** Root confirmed in both
   branches at c9c726815 (middleware emits an absolute `callbackUrl`;
   `pages/login.tsx` accepts only relative paths). The executed journey's callback was
   `/dashboard` every time, so deep-link loss was NOT captured live; it becomes
   live-evidenced only when a non-default protected destination is tested. The
   original manifest's phrasing "Deep link lost on return" should be read with this
   label.
4. **Field-set honesty**: phase2's captured `/api/auth/me` sample did not include the
   `status` field (see the field_note in the identity checkpoint); exact captured sets
   are transcribed, nothing added.
5. **Not retained / not claimed**: per-request timestamps were not retained for the
   phase1/phase2 API readbacks (approximate UTC only); the loop observation is bounded
   to 1s sampling over a 10s window; no network HAR exists. No wholesale rerun was
   needed because no decisive assertion is missing.
6. **Raw backend.log is not uploadable**: uvicorn access logs capture full session
   JWTs in WebSocket query strings (`GET /ws?token=eyJ…`, 8 lines). Only the sanitized
   excerpt (verified free of `eyJ`, `token=`, key, and password patterns) is committed;
   the raw log stays in the private scratch world. Logged-in-product observation,
   non-blocking: the access log records full bearer tokens for `/ws?token=` requests;
   worth routing to the implementation owner as log hygiene.

## Retained-world hash table (private scratch; hashes only are published)

| Path (under /private/tmp/atom-agent4-acctret-scratch) | sha256 | bytes |
|---|---|---|
| `run/atom.db` | see command record below | 8814592 |
| `run/atom.db-wal` | see command record below | 4132392 |
| `run/atom.db-shm` | see command record below | 32768 |
| `logs/backend.log` | see command record below | 108457 |
| `logs/frontend.log` | see command record below | 12523 |
| `expired_token.txt` | see command record below | 225 |
| `launch_env.txt` (NOT uploaded) | see command record below | 448 |
| `test_user_identity.txt` (NOT uploaded) | see command record below | 110 |

The exact sha256 values are recorded in the commit message of this supplement for
traceability without uploading the files themselves.

## Attribution

- Executed source: `f653c790e549` (origin/main tip post-#680), worktree
  `/private/tmp/atom-agent4-acctret`, branch `codex/agent4-account-return-20261106`,
  evidence commit `c9c726815`.
- Served backend: uvicorn `main_api_app:app`, pid 8095, `127.0.0.1:18117`,
  health-reported `git_commit f653c790e549`, started 2026-11-06T17:10:12Z;
  python 3.11.16. Frontend: Next.js dev server port 18118, node v20.19.6.
- Scratch world: `/private/tmp/atom-agent4-acctret-scratch` (own sqlite/WAL,
  LanceDB, BYOK paths; credential envs pinned empty; `BYPASS_RATE_LIMIT=1`;
  `SECRET_KEY` SHA-256 `a46b537c15980fe780f3183484e4e384d81c09cca32724e213b1f79300613d9f`).
- Test identity: `a4ret-58c87249-1106@example.com`, user `24d65258-d46d-4c72-ac9c-9d23356ac288`,
  workspace `01da977f-557b-4c81-911d-2c45c63e9be9`, role `member`. Password,
  raw tokens, cookies, and authorization headers are nowhere in this packet.

## Acceptance scope reminder

These checkpoints complete the evidence packet for the lead's acceptance decision of
the tested boundary at `f653c790e`. They do not extend the claims listed as excluded
in `EVIDENCE_MANIFEST.json` (onboarding qualification, JWT revocation, process
restart, provider/SSO, whole-app readiness). Final acceptance remains with the lead.

## Appendix: sanitized access-log excerpt (exact lines)

The excerpt below is embedded verbatim because both `*.txt` and `*.log` are
blanket-gitignored in this repo. Source: retained `logs/backend.log`
(sha256 f6ebaf21360eed228228702d955925816cb121dfcdea9b596ec73ddd3c08dc68,
108457 bytes), filtered to auth/onboarding/health request lines; verified free
of token, key, and password patterns. The raw log itself stays in the private
scratch world.

```text
INFO:main_api_app:🚀 [ULTRA LOUD] GET /health
INFO:main_api_app:🏁 [ULTRA LOUD] GET /health -> 200
INFO:     127.0.0.1:49727 - "GET /health HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/auth/register
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/auth/register -> 422
INFO:     127.0.0.1:53516 - "POST /api/auth/register HTTP/1.1" 422 Unprocessable Entity
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/auth/register
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/auth/register -> 200
INFO:     127.0.0.1:53518 - "POST /api/auth/register HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] OPTIONS /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] OPTIONS /api/onboarding/status -> 200
INFO:     127.0.0.1:54313 - "OPTIONS /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:54306 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:54313 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:54306 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:54313 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:54311 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:54306 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:53518 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:53518 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] OPTIONS /api/onboarding/update
INFO:main_api_app:🏁 [ULTRA LOUD] OPTIONS /api/onboarding/update -> 200
INFO:     127.0.0.1:56032 - "OPTIONS /api/onboarding/update HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/onboarding/update
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/onboarding/update -> 200
INFO:     127.0.0.1:56032 - "POST /api/onboarding/update HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:56032 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:56032 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/auth/logout
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/auth/logout -> 200
INFO:     127.0.0.1:57159 - "POST /api/auth/logout HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:57995 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/auth/login
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/auth/login -> 200
INFO:     127.0.0.1:58063 - "POST /api/auth/login HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:58063 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:     127.0.0.1:59013 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59012 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:59008 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59014 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59013 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59014 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59013 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:59013 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:59013 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60430 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60431 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 401
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60854 - "GET /api/onboarding/status HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:60848 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 401
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60849 - "GET /api/onboarding/status HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:60853 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60846 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60854 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:     127.0.0.1:60846 - "GET /api/auth/me HTTP/1.1" 401 Unauthorized
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 401
INFO:main_api_app:🚀 [ULTRA LOUD] POST /api/auth/login
INFO:main_api_app:🏁 [ULTRA LOUD] POST /api/auth/login -> 200
INFO:     127.0.0.1:61519 - "POST /api/auth/login HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61519 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:61531 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:61526 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:     127.0.0.1:61532 - "GET /api/onboarding/status HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61532 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61525 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61532 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61532 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61532 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/auth/me
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/auth/me -> 200
INFO:     127.0.0.1:61532 - "GET /api/auth/me HTTP/1.1" 200 OK
INFO:main_api_app:🚀 [ULTRA LOUD] GET /api/onboarding/status
INFO:main_api_app:🏁 [ULTRA LOUD] GET /api/onboarding/status -> 200
INFO:     127.0.0.1:61532 - "GET /api/onboarding/status HTTP/1.1" 200 OK
```
