# Web durable sign-out and canonical sign-in

Executed source: e173791efbb4e35021ff6d90ebde037a680e6ec6.
Backend:101 passed (including27 CI-lane controls); frontend:93 passed.
The backend XML was captured with junit_logging=no and contains no captured
stdout/stderr. Frontend JSON is a derived assertion-name/status report from
the retained successful Jest JSON; paths are repository-relative.

Confirmed negatives are summarized separately; original private logs are not
published because authentication traces may contain synthetic bearer material.

The existing RevokedToken SQL ledger now governs new HTTP/WebSocket handshakes
and refresh across processes; peer sessions remain valid. Missing database
authority refuses. Logout uses exact bearer/cookie/query precedence and verifies
its existing SQL revocation and generic audit from a fresh session. Separate
commit boundaries remain explicit; audit loss never becomes verified success.
Both existing NextAuth sign-out events perform one bounded backend notification
while allowing local clearing on failure. Active web credentials identity comes
from authenticated /me; backend owns last_login, with no fabricated subject or
parallel JS credential-metadata write. Original callback case identities remain.

The Flash read-only review used a public excerpt and no repository writes. Its
missing-callback-wrapper finding was an excerpt artifact; real imports, callback
controls and TypeScript prove registration. Cached UI identity revalidation and
cookie-only transport are distinct future hardening boundaries.

No full browser password submission, live account/provider/email/SSO, deployment,
open-socket termination, in-flight cancellation, PostgreSQL concurrency or full
app completion claim. Legacy lib/auth enrichment and OAuth JS DB paths remain
unqualified. Main web first; mobile UI last.
