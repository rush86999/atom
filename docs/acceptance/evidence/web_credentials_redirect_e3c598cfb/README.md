# Credential destination and bounded cleanup

Frozen source: e3c598cfb39e8fb63de82dbe0dcb5a4d4d5bd3c3. Both credential POST and authenticated /me
reject redirects. Final cleanup aborts any unread refused response body and
clears the single deadline timer. No fallback credential retry or alternate
identity source is introduced. Two negative controls failed on403a39173 and
pass with the repair; all108 current credential/logout/callback/login controls
and TypeScript pass. The frontend artifact is a derived result-only report.
Earlier106 and93 frontend packets overlap; do not sum these counts.

Ordinary API-first login/logout evidence stays at actual source403a39173 in
web_login_logout_browser_403a39173; it is not a served NextAuth or redirect test.
No live account/provider/email/deployment, browser password change, open-socket
termination, PostgreSQL/soak or full-app claim. Main web first; mobile UI last.
