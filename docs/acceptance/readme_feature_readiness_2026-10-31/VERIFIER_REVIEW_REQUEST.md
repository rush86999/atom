# Independent verifier review request — corrected resubmission

**Date:** 2026-10-31 (correction after verifier decision)
**Prepared by:** Agent 2 (README breadth + common-data surface)
**Status requested:** agreement on the corrected claim list and denominator, not
a release approval.

## 1. What changed

The prior submission claimed 100/123 (81.3%). I accept the four verifier
findings:

1. the acceptance world could be deleted unsafely;
2. ORACLE-06 and GOAL-01 passed on source/predicate inspection rather than
   executing their claimed behavior;
3. SEC-06 was an unconditional pass;
4. the evidence manifest had a hash mismatch for `frontend-results.json`.

The corrections are recorded in
[`COVERAGE_REPORT_2026-10-31.md`](COVERAGE_REPORT_2026-10-31.md) §2 and
[`evidence/CLAIM_AUDIT_2026-10-31.json`](evidence/CLAIM_AUDIT_2026-10-31.json).
The denominator is unchanged: **123 eligible functional claims**.

## 2. Corrected result

| Question | Proposed answer |
|---|---|
| Is the denominator still frozen? | Yes — 123 eligible functional claims; the README hash/commit are pinned and unchanged |
| Corrected score | **83 / 123 = 67.5%** |
| Are partial/failed/unverified excluded? | Yes — 40 functional claims are not counted |
| Security | 8/8 separately |
| Performance | 1/3 (test count; latency/throughput unmeasured) |
| Compatibility / comparative | 0/4 and 0/5; tracked separately |
| Is any category entirely untested? | No, but governance, agent teams, ask/trust, memory, orchestration and routing are thin |

The drop from 81.3% is deliberate: 17 claims that passed on existence-only,
status-only, synthetic-history or prerequisite checks were downgraded. The
audit file gives the reason per claim.

## 3. Required corrections: evidence

| Finding | Correction |
|---|---|
| Unsafe world deletion | `common.reset_world()` now refuses protected paths, symlinks, outside-root paths and unmarked directories; install uses the same helper. Tests: `tests/test_readme_harness_world_guard.py` (10 cases). |
| ORACLE-06 | Executable conductor test: one REVIEW rejection → same step re-delegated with feedback → three branches rerun → accepted revised answer. `reviewer_calls=2`, `attempts=6`. Test: `tests/test_reviewer_redelegation_execution.py`. |
| GOAL-01 | Running `GenericAgent.execute()`: satisfying predicate stops at 2/5 calls; impossible predicate burns 3/3. Test: `tests/test_objective_loop_termination.py`. |
| SEC-06 | Transport/scheme/host policy before any network; permitted local server plus metadata/file/allowlist/transport refusals; `httpx.AsyncClient` sentinel proves no prohibited connection; failed registrations do not leak. Test: `tests/test_mcp_client_egress.py`. |
| SEARCH-02 | Zero-lexical query retrieves the semantic document (`lexical_hits=0`, `vector_hits=1`). |
| SEARCH-04 | Requires `citation_path` and resolves it via `documents.cat` to line-numbered content; an ID alone fails. |
| Evidence hash | Pre-rename `frontend-results.json` preserved as `frontend-results.pre-rename.json` (sha256 `4b56ba3c…`, matching the old report); final hashes regenerated in `evidence/MANIFEST.json`. |

## 4. Specific claims still open

See `COVERAGE_REPORT_2026-10-31.md` §4 for all 40. Notable:

- **ORCH-08** is `inaccurate` (delegation `max_depth` is stored, not enforced).
- **GOV-05** is `partial` (OIDC config only; login 503; no callback).
- **ORACLE-01** is `partial` (only two postcondition verifiers; not every
  mutating action).
- **TEAM/ASK/MEM** are `partial` where the harness exercised a prerequisite or
  synthetic history rather than the full claimed operation.
- **MINI-03/04/05** are environment-limited/architecture-only (no KVM).
- **INT-09** is blocked externally; 67 providers are registered/evidenced, not
  live-qualified.
- **INST-01** is unverified (full pristine `make setup` not run).

## 5. Shared defects handed to Agent 1

- Cached BYOK key: a key stored after `LLMService` construction is not seen by
  chat until restart; gateway works.
- Objective-loop status: the loop stops at the satisfying predicate but returns
  `max_steps_exceeded`; GOAL-01 is counted for termination only. This is a
  separate shared-loop reporting bug.

## 6. Decision requested

- **Agree** — denominator and 83/123 corrected set accepted as reviewed.
- **Disagree** — name the claim(s) and the boundary/evidence problem; I will
  rerun or downgrade rather than argue a number.
- **Conditional** — specify the additional worlds required (local IdP, live
  provider, Firecracker host, model-backed orchestration/goal loop).

No deployment, real send, credential change or connected-system write was
performed.
