# Canvas submit compatibility checkpoint

Executed source: cc7538142. Python 3.14 and 3.11: 37 controls passed each (32 receipt/scope/authority controls plus 5 legacy public-route callers). Current DB User, Canvas, audit and CAS are real scratch SQLite; authentication dependency is controlled, not real login/JWT qualification.

Preserves established Personal None/default agent workspace compatibility without admitting a real foreign workspace. A null principal cannot borrow a real foreign tenant. Governance refusals retain the established nested error code with additive receipt metadata. Persistence failure is now a truthful 503, rather than the old unsafe 200-success expectation.

The retained legacy negative ran at a80a7cff1: 3 failed / 2 passed. Two failures exposed compatibility regressions; the third was the obsolete nonfatal persistence expectation, deliberately corrected. Python 3.11 first stopped during pytest configuration because its retry plugin tried to bind a local socket; the successful run disables that retry plugin (no tests skipped, no retry or application gate bypass).

Normal producer negative ran at runtime 49fa04dfe with test bytes committed unchanged at a80a7cff1: 2 failed. present_form returns an unpersisted Canvas id; this is a genuine normal-path integration gap. It remains open and the branch is not ready to merge. No browser, live login, PostgreSQL, native mobile or general app completion claim follows.
