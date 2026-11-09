# Ordinary web login and sidebar sign-out

Executed revision403a391738a4ee8401ffa5cfe4b30609bac7e778. The normal main
backend and ordinary frontend used a fresh owned SQLite world, core profile,
offline/local-only configuration, disabled schedulers and captured SMTP only.
Optional frontend PostgreSQL was explicitly unavailable on an isolated port; no
live database could be used. One synthetic member was registered through the
normal scratch API, then signed in through /auth/signin to /dashboard. Escape
dismissed the fresh welcome dialog; no onboarding-completion claim is made.
The sidebar Sign out returned to /auth/signin; independent SQL readback finds
one exact session revocation and one actor/workspace/session/operation-bound
logout audit. An independent registration-issued peer bearer still returns200.

The signed-in screenshot precedes logout; the final destination was verified by
the browser accessibility state. Browser storage is unavailable in the read-only
evaluation scope, so no browser bearer was exported. No exact-browser-token
HTTP replay or process-restart claim is made for this episode. Native new-process
refusal remains separately covered by the e173791ef packet. This UI uses the
existing API-first login flow, not the NextAuth credentials provider.

The actual health identity is dirty, not clean: first health capture occurred
after Next generated next-env.d.ts and .next-session build files. Those exact
dirty/untracked labels are retained. No product source was edited during the
episode. The generated type file was restored only after both processes stopped;
192751767 disposable build bytes were removed and private DB/evidence retained.

No password change, live account/provider/email/model, deployment, PostgreSQL
concurrency or full browser recovery claim. API-first logout outage/deadline
behavior remains a separate source-diagnosed boundary. Main web first.
