# Password recovery browser episode on repaired source

- Frozen source: `f9ef079c2a2805dc1a92b91a94a9ff2a82bd9b1b`
- Executed app bytes: Next `16.2.2`, Node `v20.20.2`, build id `SB4Z5gPHOVhvOVdm4Vytd`
- Build: existing heavy gate -> `next build`, exit `0`, `27.0s`, owned dist removed
- Harness executed: `browser_recovery_reset.py`, sha256 `23f5d3d8e2432d3017fd1efe5fb282e3ae7e51d534d85508715e8258b0caf5b3`
- No product edits in this packet.

## Command

```text
python3 /private/tmp/root-web-recovery-reset-browser-20261109.py
exit 0
```

## Required flow

- Fresh Playwright context, no navigation: cookies empty.
- Static same-origin asset before app bootstrap: localStorage and sessionStorage keys empty.
- Signed-out `/auth/forgot-password`: 200, ordinary UI form, one forgot request, success message.
- Private local mail capture (no SMTP): reset link/path present; token never printed.
- Ordinary navigation to captured `/auth/reset-password?...`: 200, valid form, one verify-token and one reset request, success and redirect to `/auth/signin`.
- Old password through ordinary UI: refused; no SDK session cookie and no session user.
- Old password through canonical backend: `401`.
- Reset token after use: `valid=false` (consumed).
- New password through same ordinary UI: dashboard, `__Secure-next-auth.session-token`, HttpOnly, Secure, SameSite=Lax, 5-segment JWE, not raw bearer; canonical `/me`, session user, and decoded SDK id all equal the registered scratch account and final DB id; same backend generation.
- Scratch DB: one user row, same account ID before/after.

## Freshness detail

`freshness` records the pre-navigation empty context and empty same-origin storage before app bootstrap. `signed_out_state` records only names after app load:

- cookies: `__Host-next-auth.csrf-token`, `__Secure-next-auth.callback-url`
- localStorage: `nextauth.message`
- no `auth_token`, no SDK session cookie, no session user

No app data was deleted or injected to manufacture emptiness.

## Harness history

- v1 `e3d8b66fa925f5eec0f82fa9bb3dec433c18b020192c34fcd3d21dd174933f67`: limited positive; reset flow passed, but freshness was measured after app bootstrap and exact account binding was not explicit. Not a product failure.
- v2 `496dba2d70fe31aa26ab7e2e59dc6f7b025dc5d3202dbe40b08be77f97c9102f`: limited positive; exact account binding added, freshness still after app load.
- v3 `23f5d3d8e2432d3017fd1efe5fb282e3ae7e51d534d85508715e8258b0caf5b3`: corrected focused successor, the executed harness in this packet.
- Both v1/v2 private packets and worlds are retained; product source is the same `f9ef079c2` for all.

## Disclosures

- `TESTING=1` runtime with fixed scratch `DATABASE_URL`/`ATOM_DATA_DIR`; wrapper used `TESTING=0` only during `main_api_app` import so the explicit fresh DB was honored, then restored `TESTING=1`.
- HTTP loopback only; no TLS/production-transport claim. Chromium accepts the Secure cookie on loopback.
- SMTP was replaced by private file capture; no live email was sent.
- No provider/model calls, consent, sends, spend, deployment, PR, merge or force-push.
- No full signup/onboarding/reload campaign repeated; this is the targeted recovery slice.
