# Budget denial precedes ordinary maturity review

Executed final source: `5adcd9dd3`; implementation `171ba856d`.

The independently corrected 96-case policy matrix failed 12 cases at predecessor `25115124b`: Student/Intern maturity denials returned ordinary review before observing configured exhausted hard/soft stops. The repair checks budget restrictions for otherwise reviewable actions, without changing unknown-agent/nonreviewable refusals. An actual GenericAgent → governance → real MCP consumer twin now refuses the hard stop before entering ordinary human review and produces no business effect/audit/HITL row.

Final gate: **142 passed**, actual exit 0. Matrix spans four maturity tiers, four budget modes, sync/async/sync-in-async callers and exhausted/available budgets. Under-budget maturity behavior remains intact. Approval-mode budget review remains intentional; this does not qualify its eventual financial effect. Existing governance callers: **54 passed, 1 known baseline failure**, actual exit 1 (`test_covpush_w29_governance.py::TestRegistry::test_register_new_agent`, stale confidence expectation). Earlier broader 146-pass/1-failure/1-skip evidence remains attributed to `cda63def4`, not this successor.

`negative-probe.py` is the valid independent probe used for the 12-failure/84-pass capture. An earlier private prototype used an undeclared level-2 action while expecting level-3 maturity behavior; that fixture-invalid 36-failure output is retained privately and is not product evidence. No action allowlist was relaxed.

Raw logs, commands, actual exits and JUnit files are retained without regeneration. Final/current source hashes bind below. Predecessor packets are preserved unchanged. Scratch SQLite and controlled model transport only; no live model/provider/account change or spend. PostgreSQL, concurrent spend admission, financial failure degradation and full-app completion remain unqualified.
