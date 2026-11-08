# Shared automation worker boundary

Frozen integrated source: `95596482eb3b239dd72ceba9abc04af8852aaee2`; runtime checkpoint2792bd6df. Accepted main0887737ac has exactly reference330c0e758's tree. The history integration resolves duplicate squash hunks without changing any byte of the200-control successor tree.

Stage/fleet scheduled loops and manual routes performed synchronous work on the application loop. Shared stdlib helpers in core.asyncio_compat now preserve ContextVars, keep each owner's separate gate until actual worker exit, convert escaping StopIteration, and route notifications to the originating loop. Org-politics consumes the same helpers. Authentication, modes, consent, certification/verdict logic and database ownership remain unchanged. No new executor/store/router/approval lifecycle.

## Evidence

- Existing reference selection:168 passed/1 obsolete cache-test failure on each runtime.
- Unmodified native proposal:30 controls pass, but independent executor-fallback probe fails because caller context and original loop are lost. The original proposal and negative are retained.
- Corrected fallback: independent probe passes;31 new controls pass.
- Broader candidate initially retains the same obsolete cache-test failure. A type-only adjustment exposes its second obsolete assumption: the deliberately removed separate async lock. That unsafe dual-lock design was not restored. The same test identity now verifies that real sync and async operations enter one native guard. Intermediate failures remain retained.
- Final affected selection:200 passed on Python3.11 and3.14. All11 candidate file hashes in the actual precommit run specs match this frozen source. Base330 and original logs are not relabelled as clean final-commit runs.
- Existing certification/policy functions remain AST-equivalent; only scoped wrappers, loops and scheduling branches change. Required CI preserves previous modules and adds the affected neighborhood.

Native DeepSeek Flash authored from verified public source only and hit its35-step bound; root audited, corrected and executed it. Reference files are unchanged. Actual controlled tests include imported stage/fleet consumers and their real route functions with owned passes doubled, plus real scratch SQLite org finding/fresh-session controls. They do not certify HTTP authentication, live notifications/models/providers, elapsed overnight scheduling, distributed exclusion, PostgreSQL, soak or general autonomous judgment. Cancellation of an awaiter never claims a physical stop of its worker. Accepted earlier scopes and historical scores remain unchanged.
