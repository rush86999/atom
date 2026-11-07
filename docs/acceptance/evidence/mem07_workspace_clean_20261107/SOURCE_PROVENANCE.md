# Source attribution

Final complete-source tests ran at `cf2964720e17`, with runtime repair `f0efc7caadc2` and committed seam controls `eb8b4578cac6`. Baseline `248a2329623b` had 345 passed /23 failed; final source had347 passed /the exact same23 failure IDs. Independent lead suites/probes25passed.

The intermediate corrected run had runtime f0efc7caadc2 plus uncommitted test controls later recorded in eb8b4578cac6. Its worktree was not clean. It is retained as intermediate evidence, not attributed to the complete committed tree at f0efc7caadc2.

Failure-first evidence substituted only `backend/core/auto_dev/reflection_engine.py` from `54cd12bf20c8` into the corrected harness, then restored it. The complete old runtime was not replayed. Other helpers/tests stayed at the corrected harness checkpoint.

All six runtime/test files in this clean successor are byte-identical to the executed cf2964720e17 files. CI is independently reconciled against current main and adds both MEM07 suites. No old green check is inherited by the successor. The manifest preserves source hashes against the actual executed old checkpoint, not a fabricated new execution identity.

PR709 scanner incident39776814 pointed at a Git commit identifier in expanded provenance, verified using git rev-parse. Original branch retained; no history rewrite, secret rotation or scanner waiver.
