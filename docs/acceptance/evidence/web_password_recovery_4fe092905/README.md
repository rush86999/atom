# Web password recovery — API and component checkpoint

The canonical auth consumer now creates links for the implemented page, refuses globally unavailable mail, binds current account plus one-use token in a conditional transaction, independently checks persisted credentials, and invalidates other outstanding recovery links after success. Issuance claims the account snapshot to serialize with reset. No new database, table or credential engine is introduced.

Frontend recovery proxies call only the configured Python service and preserve refusals. The former direct PostgreSQL fallback is removed. UI success requires a verified receipt; delayed requests cannot update a changed token page or redirect after unmount. Missing mail does not masquerade as delivery. Normal login remains required.

Qualification:102 backend/auth/CI-preservation controls on committed source;87 frontend controls; TypeScript exit0. Three delayed-response controls failed before the navigation fix. All original API test identities remain, with obsolete parallel-writer expectations replaced by explicit no-local-write/backend-forwarding assertions. The initial route diagnosis was corrected after tracing main's dynamic registry; no missing-main-route claim is made.

Backend tests ran after the code freeze. Frontend tests ran before the commit with the identical source bytes now recorded here. SMTP is a memory double, not live delivery. Existing bearer-session invalidation and an ordinary normal-app browser/mail-capture journey remain open. This packet supports API/component behavior only, not full account-security or whole-app completion.

Engineering reference: [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html). Economy CLI read-only review corroborated the navigation issue; its advice was independently reproduced with failing controls before implementation. No live account, mail, provider, deployment or spend action occurred.
