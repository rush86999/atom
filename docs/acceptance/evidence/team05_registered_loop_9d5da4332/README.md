# TEAM-05 registered-loop join

Executed source: `9d5da4332`. Python 3.14. Scratch SQLite and controlled transport; 31 tests passed across the registered-loop, scheduled-entry and automation suites.

The actual registered automation task drives the real automation pass and real certification consumer into a durable pending consent row, read using a fresh database session. Repeated ticks do not duplicate work; off mode registers no task; privilege flags stay disabled. Only model chat transport, external notifications and waiting intervals are doubled. Fixture teardown restores the caller's original module state.

This closes the controlled registration → pass → durable finding join. It does not prove elapsed overnight timing, main-app startup, live model judgment, PostgreSQL, multi-worker or general app completion. Historical 111/123 and alignment gap 3.0 remain unchanged. No app-model call, policy enablement, deployment or live-account action occurred.

`focused-tests.log` is the inspected captured output with local worktree/interpreter paths replaced. Its private original remains at `/private/tmp/team05-final-private.log`. Secret-pattern inspection found no JWT, Bearer token, token query or known fixture secret. No result was regenerated to fit a hash.

## PR 868 — offline scheduled configured dispatch (merged `d1be5e816`, 2026-11-11)

PR #868 "Verify scheduled alignment routing and durable consent" (branch
`codex/team05-scheduled-routing`; commits `70d924576` + `dc21d8fd4`) merged as
`d1be5e816a83c095bbf7894471797bbf3c241d20` (2026-11-12 04:36 UTC / 2026-11-11
23:36 -0500). All **13 PR checks were green** at merge — confirmed through the
GitHub check-runs API on head `dc21d8fd4f79aee8d01abd44287d93c0db7a51b4`,
every run `success`: `backend-core`, `backend-oracle`, `backend-tests`,
`quickstart`, `quickstart-install` (3.11 / 3.12 / 3.13), `frontend-typecheck`,
`syntax-gate`, `e2e-journey`, `full-app-boots`, `docker-build` and the
GitGuardian security check.

The merged regression (`backend/tests/test_org_politics_scheduled_worker_offline.py`,
406 new lines, plus an additive backend CI step "Run offline scheduled
alignment dispatch controls" mirrored in
`backend/tests/fixtures/ci_backend_additions.json`, run with `TESTING=1` and a
scratch `DATABASE_URL`) closes the join the registered-loop control above left
open: the production **configured dispatch** seam. The accepted loop control
replaced `_default_chat_fn` outright; this one drives the real chain

```
registered task -> org_politics_automation_loop
    -> run_auto_certification_async (real worker thread + gate)
    -> run_auto_certification -> certify -> alignment_verdict
    -> _default_chat_fn() -> BYOKHandler.generate_response(...)
    -> ranked eligible route -> SDK client chat.completions.create
```

with the **real scheduler and real BYOK**, only the SDK leaf controlled:

- **Real scheduler**: the actual registered automation task drives the real
  automation pass through the real nightly interval (the 1440-minute —
  86,400-second — interval is asserted on the controlled tick clock; one real
  pass per tick), and `ensure_automation_task` does not double-register the
  loop task.
- **Real BYOK**: the real `BYOKHandler` constructor, `generate_response`, route
  ranking/eligibility and provider policy run unchanged; the handler's
  recorded `_last_used_provider`/`_last_used_model` match the configured route
  (`opencode-go` / `deepseek-v4-flash` — test-catalog identities) and
  `provider_policy.allows(...)` is asserted directly.
- **Controlled SDK**: only the configured client's `chat.completions.create`
  leaf is scripted — request construction, route admission, accounting, usage
  attribution and parsing remain the handler's. The provider credential and
  pricing inputs are test doubles, and a fresh full-schema **scratch SQLite
  file is the real persistence boundary** (read back through a brand-new
  session, never dev data).

**Durable pending consent (approved twin).** With the configured provider
allowed by installation policy, one real pass issues 18 SDK calls (3
adversarial scenarios × 3 org structures × proposal + judge; 9 of them judge
calls), and files exactly three pending consent rows in the scratch file —
`state=approval`, `verdict=enable`, `mode=approve`, one per flag key
(`skill_trust`, `allocator_integrity`, `org_privileges`) — read back from a
fresh database session. `resolve_flag_value` stays `False` for every flag
while approval is pending (consent requested, never assumed); notifications
are `approval_needed` only; the sweep records ran/green/evidence_complete
true.

**Durable denial (denial twin).** The client stays configured but
installation policy selects a different provider, so no route is eligible:
zero SDK calls, zero pending consent rows, zero notifications, sweep green
false / evidence_complete false. Policy denial happens at the real handler's
route gate, before any transport attempt.

**Still unverified** (the test module's own boundary notes, retained here):
no live configured-provider or served-model evidence — the SDK completion
leaf is doubled and credentials are test-only; no 24-hour soak or wall-clock
night-timing observation — the scheduler clock is a controlled tick; not
PostgreSQL, multi-worker or distributed-lock evidence; no production setting,
flag or policy changed outside the test process.

**Status grades unchanged**: TEAM-05 remains **partial**. This merged PR
extends the controlled seam from the registered loop to the configured
dispatch boundary, but **live provider** and **overnight (elapsed) timing**
evidence remain outstanding. Historical 111/123 and alignment gap 3.0 are
unchanged from the sections above; no acceptance grade anywhere in this
document is altered by PR 868.
