# MEM-07 source-bound evidence (2026-11-06)

Branch `codex/mem07-error-candidate-20261107`, successor of PR #709.
Executed source at verification time: merge head `cf2964720e17`
(owned fix commit `f0efc7caadc2`; base-main baseline
`248a2329623b`).

## Defect and repair (scope)

**Defect (MEM-07):** Auto-Dev gating for the tool-error → pending-candidate flow
consulted the *first workspace row by tenant* instead of the agent's own
authoritative workspace binding. A tenant can hold many workspaces with
different opt-ins, so (a) an agent whose own workspace never opted in could be
processed/enabled for evolution when the first workspace by tenant opted in,
(b) a missing or inconsistent agent↔workspace binding was silently allowed.

**Repair (`f0efc7caa`):** general resolver
`AutoDevCapabilityService.authoritative_workspace_settings(agent_id, tenant_id)`
— returns the workspace `metadata_json` for the agent's own binding, or
`None` (fail closed) when the agent row is missing, the binding is blank, the
workspace row is missing, or the tenant disagrees (legacy unset-`tenant_id`
rows tolerated). Both consumers rewired to this resolver:

- `ReflectionEngine._should_process_agent` (episode-time gate)
- `_live_fix_opted_in` (real-time live trigger gate)

`_get_workspace_settings` is kept only as a deprecated non-gate fallback and
its former gate callers in tests/coverage suites are retargeted to the
authoritative resolver (`eb8b4578c`); per-file fail-closed seam controls were
added (`test_should_process_agent_refuses_when_authority_missing`).

`8748f9033` adds the two focused MEM-07 suites to `.github/workflows/ci.yml`.
The post-merge CI resolution (`cf2964720`, merge of origin/main incl. PR #704)
is additive: every main gate retained (incl. `test_recording_review_scope.py`
and the served-route step) plus the two MEM-07 suites. The merge introduced
zero delta in the owned source files (`git diff 8748f9033..cf2964720` over the
six owned files is empty; blob hashes identical, see `SOURCE_PROVENANCE.md`).

## Evidence artifacts

| file | what it is |
| --- | --- |
| `baseline_neighborhood.sanitized.log` | baseline neighborhood run at `248a23296`: 23 failed / 345 passed |
| `candidate_corrected.sanitized.log` | intermediate run with runtime `f0efc7caa` and uncommitted seam-retarget controls later committed in `eb8b4578c`: 23 failed / 347 passed |
| `candidate_preretarget.sanitized.log` | intermediate run at `f0efc7caa` before seam retargeting: 25 failed / 343 passed — the 2 extra failures are exactly the stale-seam tests, removed by `eb8b4578c` |
| `candidate_mergehead.sanitized.log` | neighborhood re-run at merge head `cf2964720`: 23 failed / 347 passed |
| `focused_mergehead.sanitized.log` | focused suites at merge head: 13 failed / 43 passed — failures are all the pre-existing baseline stale-symbol subset; both MEM-07 focused suites and every seam control pass |
| `failure_first.sanitized.log` | defect demonstration at byte-exact pre-fix source `54cd12bf2`: 5/5 workspace twins fail with the refusal direction shown |
| `failure_id_comparison.json` | programmatic failure-ID set comparison (see below) |
| `SOURCE_PROVENANCE.md` | exact source binding: commit/blob/sha256 triples with Git-object verification |

## Sanitation (labeled)

All captured logs were sanitized before publishing:
`/Users/<home>` → `<home>`, `rushiparikh` → `<user>`. A residual scan for the
username and home path ran on every published artifact (`pii_residual: false`
for all seven). Raw originals stay private outside the repo; nothing was
uploaded uninspected. This README labels the sanitation explicitly.

## Exact baseline/candidate failure-ID comparison

`failure_id_comparison.json` compares the SHORT TEST SUMMARY `FAILED <id>`
sets extracted from the sanitized originals:

- baseline `248a23296` (23 failed) vs corrected `f0efc7caa` (23 failed):
  **ID sets identical** (empty symmetric difference).
- baseline vs merge head `cf2964720` (23 failed): **ID sets identical** —
  the set of remaining failures is fully inherited from baseline; the two
  new seam controls and all MEM-07 twins pass.
- pre-retarget intermediate `25 failed` → the two extra IDs are exactly
  `test_covpush_autodev_comms.py::TestReflectionEngineCoverage::test_should_process_agent`
  and `test_covpush_w84c_autodev2.py::TestReflectionEngine::test_should_process_agent_true`
  — both stale `_get_workspace_settings` seam tests, resolved by the `eb8b4578c`
  retargeting, not by skipping or waiving anything (zero skips, zero waivers,
  no test deleted).

## Failure-first demonstration

`backend/core/auto_dev/reflection_engine.py` was reverted to byte-exact
`54cd12bf2` content (`git diff --stat` against that commit produced empty
output), the five workspace twins were run against it, and all five failed
for the intended direction (see `failure_first.sanitized.log`):

- the live trigger fired for agents whose own workspace was disabled/orphaned
  (`agent-twin`, `agent-orphan`, `agent-cross`) because the first-workspace
  fallback opted them in;
- missing/inconsistent authority produced `sqlalchemy.exc.NoResultFound`
  instead of a fail-closed refusal.

The working tree was then restored byte-exactly to the fix (`git status
--porcelain` clean against merge head). The twins run exclusively against
scratch SQLite — never the live dev DB.

## Boundaries

- Scratch SQLite worlds only; no live DB, no deployment, no external calls.
- Scope limited to: the resolver, the two consumer gates, seam retargeting on
  the two coverage suites, the five workspace twins + controls, and CI
  additivity. No unrelated families touched or claimed.
- No merge, accept, approval or self-review; PR #709 is pushed for
  independent exact-head checks by the integrator.
- The integrator's independent focused-suite run (25 passed at `f0efc7caa`,
  log `/private/tmp/root-mem07-fixed.log`) is cited as independent
  verification. That log is **not committed** and remains private; this
  directory contains only this session's own sanitized logs.
- Bootstrap scratch files (`.mem07_pr_body.md`, `CLI_WORK_ORDER.md`,
  `opencode.jsonc`) stay untracked.

## Provenance precision added by the lead

The intermediate corrected run was **not a clean-tree run**: runtime files matched `f0efc7caa`, while seam-retarget test controls were uncommitted and subsequently recorded in `eb8b4578c`. The 347-pass intermediate result must not be attributed to the complete committed tree at `f0efc7caa`. The final neighborhood and focused runs are bound to the complete source/test checkpoint `cf2964720`; original log bytes are preserved.

The failure-first demonstration used a **single-file substitution**: `reflection_engine.py` matched `54cd12bf2` exactly, while the corrected harness/tests and capability helper remained present. It was not a full checkout or whole-runtime replay at `54cd12bf2`. The file was restored before the final commit. This qualification changes attribution only; no test output was regenerated.

## Clean-history successor

The security detector on superseded PR #709 flagged the value of `authoritative_final_checkpoint` in its expanded provenance JSON. The lead verified that value exactly equals the Git commit identity of the tested checkpoint `cf2964720e17`; it is not credential material. This clean main-based successor retains the runtime/tests byte-for-byte, uses ordinary short Git references for provenance and the standard SHA-256 source/artifact manifest, and omits the redundant expanded JSON. The original branch/history and logs remain preserved. No waiver, credential action, force push or original-log rewrite occurred. Fresh hosted checks apply to this successor only.
