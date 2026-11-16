# SMTP certificate validation — November 16, 2026

Configured SMTP now uses Python's default TLS context to validate the server
certificate chain and hostname before authentication or message delivery.
An actual owned-server reproduction showed the prior bare STARTTLS call
accepted an untrusted self-signed server that a verified context rejected.

The shared helper serves password-recovery background email and opted-in
high-priority notification email. Untrusted or wrong-hostname certificates
now return failure through the existing exception path before login/send.
There is no insecure option, plaintext fallback, retry or provider branch.
The existing unconfigured legacy helper behavior and recovery-readiness
gate are unchanged. Recovery HTTP200 accepts a request asynchronously; it
does not, by itself, prove delivery. Notification code consumes the helper's
boolean result. Do not confuse either with a delivery receipt.

The repair at source 56e410f2588ca353d437aaf603426ff883391b00 passed 94
independent SMTP/recovery checks in 25.98 seconds with networking denied and
an explicit scratch database. A new actual Mailpit server independently
proved all three cases: untrusted chain refused with zero messages; a
trusted certificate with the wrong hostname refused with zero messages;
trusted correct hostname delivered exactly once. The owned server stopped.
The positive used a public test CA through standard SSL_CERT_FILE; no global
trust setting was changed. Hostname validation remained enabled.

Operators using private SMTP CAs must configure the installation's trust
store or standard SSL_CERT_FILE/SSL_CERT_DIR. Do not disable verification.
Public-provider delivery, all notification integrations and production
operations are not established by this synthetic local transport check.
The earlier ordinary browser account lifecycle has its own source-bound
record and is not silently reattributed to this repair.

[Filtered result](evidence/smtp_certificate_validation_20261116/result.json).
Primary reference: [Python 3.12 TLS contexts](https://docs.python.org/3.12/library/ssl.html).

The independent scratch gate selected tests/test_email_utils_tls_validation.py, tests/test_covpush_w78_email_utils.py and tests/test_web_password_recovery_contract.py. TESTING=1, PYTEST_VERSION and an absolute scratch DATABASE_URL were set before imports, with all network access denied.
