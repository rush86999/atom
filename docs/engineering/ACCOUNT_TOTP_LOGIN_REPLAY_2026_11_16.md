# Account authenticator enrollment and login replay verification

Status: independently qualified at the recorded candidate before merge; release ancestry is tracked in the readiness index. Full app scope remains 143 claims across 18 goals; this is partial Goal 1 evidence.

Canonical password/TOTP login previously verified a code directly, bypassing the durable replay fence already used by menubar login and factor mutations. Candidate `268efd405d72361456e759537fa4b47168fa25ea` routes canonical sign-in through that shared verifier. Only a verified result authorizes token issuance. Invalid codes remain rejected; consumed steps return 409; uncertain verification returns 503 without a token. Password-only challenges and accounts without a factor retain their normal behavior.

This follows [PyOTP guidance](https://pyauth.github.io/pyotp/) to persist accepted counters and reject their reuse; no new OTP implementation or dependency upgrade was introduced.

Independent verification:

- 122 adjacent login, menubar, factor-write and rate-limit controls passed in 64.40 seconds using scratch databases with network access denied.
- Three replay controls fail against the original source: repeated sign-in, an enrollment-consumed step, and a previously accepted later step. They pass against the candidate.
- An injected commit exception inside the real shared helper returns 503 without invoking token creation, and rolls back the consumed step. This is fault injection on a real scratch SQLAlchemy session, not a physical storage failure.
- In a fresh isolated app, ordinary browser password sign-in, enrollment from the displayed manual secret, recovery-code panel, logout, password-only challenge, wrong-code refusal, later real-time code sign-in, native-prompt disabling and disabled-state reload all passed. Challenge and invalid-code attempts left the web session unauthenticated.
- Immediately after successful authenticator sign-in, a fresh context submitted the same accepted code to the public login API within the same real 30-second step. It received 409, no token and no authenticated web session.

The API ran clean candidate source. The reused production frontend was built at `97e43a6b18a676a867b4e1e86f3b0c22da74461d`; its entire tracked frontend tree is identical to this candidate. No rebuild is claimed. Both disposable app services were stopped and their absence checked.

No auth cookies, bearer tokens or browser storage were injected; no request interception, fake HTTP, database-secret lookup, forced browser time or app model calls were used. Secrets and actual authenticator codes stayed in process memory. The public replay negative is an API check, not an additional browser-form submission.

This does not prove SSO, recovery-code sign-in, concurrent login races, all deployment profiles, production readiness or completion of Goal 1. Filtered evidence belongs beside this document at publication. Publish only after reconciling the actual merged parent and fresh required CI; do not attribute this runtime to an unexecuted future commit.

[Filtered result](evidence/account_totp_login_replay_20261116/result.json).

The owner-approved test-only follow-up `87f019af2604e0b09d5ae5ecee624d570f28bbe8` adds that real-helper commit-exception case permanently and closes its scratch client/session/engine. Independent focused verification passed41 checks in16.73s. Production code remains identical to the browser-verified candidate; this adds no new runtime claim.
