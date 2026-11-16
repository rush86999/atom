# Ordinary browser account lifecycle — November 16, 2026

At source 97e43a6b18a676a867b4e1e86f3b0c22da74461d, one fresh synthetic
account passed ordinary signup, authenticated dashboard, session reload,
normal logout, protected-route denial and normal login again. The actual
browser context's web-session identity matched that account.

The same account completed forgot-password UI, received the actual message
through an owned local SMTP server, followed its reset link and completed a
verified reset. The consumed link was refused. The old password returned 401
with a visible error; the new password returned 200, reached the dashboard
and established the correct web session. The token came only from received
mail, never from the database or logs. No auth/storage/cookie injection,
route interception or fake mailer was used.

The backend restarted with the same source, database and user count to
configure SMTP. Checksum-verified Mailpit 1.33.1 required STARTTLS and a
specific synthetic credential; plaintext and wrong authentication were
independently refused. No relay was configured and outbound networking was
denied. Mail used the SQLite memory URI and its placeholder remained zero
bytes after receipt. Journey credentials stayed in anonymous pipes/process
memory. This tests local transport, not external deliverability or production
certificate-chain validation.

The isolated Webpack build passed in 96.321 seconds with cached APFS
copy-on-write dependencies. Runtime identity was
97e43a6b18a6-dirty.7d401fa39a75; only Next.js's generated type reference was
a tracked delta. The core profile and selected-empty provider policy were
used; no inference or dependency installation occurred. All owned app/mail
services stopped and absence was verified; world/evidence remain local.

Earlier harness failures are retained: a nonexistent onboarding Close
button was replaced with the actual Escape handler, and the login-response
waiter was corrected to the configured direct-backend origin. Completed
signup/reset mutations were not replayed against those accounts; a fresh
actor passed the full sequence. A pattern check found no reset-query/JWT
matches in 23 owned logs; that is not a general secret audit.

SSO, browser TOTP/account deletion, rate-limit breadth, real one-hour expiry
and other deployment audiences remain outside this journey. It does not
complete whole Goal 1 or regrade the original 143 claims/18 goals.
[Filtered result](evidence/account_browser_lifecycle_20261116/result.json).

The later SMTP certificate-validation repair is measured separately in [the SMTP certificate-validation record](SMTP_CERTIFICATE_VALIDATION_2026_11_16.md); this browser episode retains its original source and locally generated server certificate.
