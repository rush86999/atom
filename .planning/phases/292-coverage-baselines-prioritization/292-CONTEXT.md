# Phase 292: Coverage Baselines & Prioritization - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Measure and validate accurate backend and frontend test coverage baselines, then generate
prioritized high-impact file/component lists to guide coverage expansion in Phases 293-295.

**This phase does NO coverage expansion** — it only measures what exists and prioritizes
what to fix next.

**Depends on Phase 291** (frontend tests must reach 100% pass rate before frontend
coverage can be accurately measured).
</domain>

<decisions>
## Implementation Decisions

### Baseline measurement
- **D-01:** Backend baseline MUST be re-run from scratch using `pytest --cov=core --cov=api --cov=tools`. The 18.25% figure from v10.0 is a reference point, not authoritative — the fresh run IS the baseline.
- **D-02:** coverage.json output MUST pass both structural validation (all required fields present: `meta`, `files[].executed_lines`, `files[].summary.percent_covered`, `files[].missing_lines`, `totals`) AND a percentage number check. Malformed or incomplete output is rejected.
- **D-03:** Frontend baseline measurement BLOCKS on Phase 291 completion. Do NOT measure frontend coverage until all 1,504 tests pass (100% pass rate). Jest's standard `--coverage` flag is sufficient.

### High-impact file prioritization
- **D-04:** Backend high-impact files use LAYERED tiers:
  - **Tier 1 (must-fix):** <10% coverage, >200 lines
  - **Tier 2 (should-fix):** 10-30% coverage, >200 lines
  - **Tier 3 (nice-to-fix):** 30-50% coverage, >200 lines
- **D-05:** Reuse existing prioritization infrastructure — `prioritize_high_impact_files.py` and `business_impact_scorer.py` — with updated coverage data from the fresh run. Formula: `priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)`.
- **D-06:** LOC cutoff stays at >200 lines (matches ROADMAP). Business impact tiers from existing `business_impact_scores.json` (Critical/High/Medium/Low) are authoritative.
- **D-07:** Frontend components are prioritized by BUSINESS CRITICALITY first — Canvas, Chat, Agent Dashboard, Integrations — with coverage percentage as a secondary factor.

### Deliverables
- **D-08:** All high-impact file lists must be delivered in BOTH JSON (for downstream programmatic consumption by executor scripts) AND Markdown reports (for human review, archived in `coverage_reports/`).
- **D-09:** Final deliverables to produce:
  1. Backend baseline report (coverage percentage + structural validation results)
  2. Frontend baseline report (coverage percentage after 291 completes)
  3. Backend high-impact file list (JSON + Markdown, layered by tier)
  4. Frontend high-impact component list (JSON + Markdown, ranked by business criticality)
  5. Coverage measurement methodology validation document

### Acceptance criteria
- **D-10:** All 5 ROADMAP success criteria must be met, PLUS:
  - Cross-check: backend and frontend lists target complementary (non-overlapping) files
  - JSON output is parseable by standard `json.load()` without errors
  - Measurement methodology documented so Phases 293-295 can reproduce results
  - Fresh coverage run completes without errors (exit code 0)
  - Structural validation passes on every coverage.json output file

### Claude's Discretion
- Whether to modify existing scoring scripts vs write wrappers
- Exact output file paths for baseline reports (reuse existing `coverage_reports/metrics/` directory)
- Frontend measurement configuration details (Jest flags, coverage collection paths)
- Exact acceptance criteria thresholds for what constitutes "accurate"
- How to handle the case where Phase 291 is partially complete (document the gap, don't measure frontend)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Coverage measurement methodology
- `backend/tests/coverage_reports/metrics/MEASUREMENT_METHODOLOGY.md` — Official measurement procedure, common mistakes, verification commands
- `backend/pytest.ini` — Backend coverage configuration (source paths, omit patterns, branch coverage, fail_under thresholds)
- `frontend-nextjs/jest.config.js` — Frontend coverage configuration (collectCoverageFrom, coverageThreshold, phase-based thresholds)

### Coverage infrastructure (existing — reuse, don't rebuild)
- `backend/tests/scripts/prioritize_high_impact_files.py` — File ranking by priority_score formula, generates high_impact_files.json
- `backend/tests/scripts/business_impact_scorer.py` — Business impact tier assignment (Critical/High/Medium/Low)
- `backend/tests/scripts/coverage_trend_tracker.py` — Historical trend tracking, regression detection
- `backend/tests/scripts/generate_coverage_dashboard.py` — HTML dashboard generation from coverage data
- `backend/tests/scripts/measure_phase_165_coverage.py` — Example phase-specific measurement script (reference pattern for Phase 292 script)

### Existing analysis and baselines
- `backend/tests/coverage_reports/HIGH_IMPACT_FILES.md` — Previous v5.0 high-impact file analysis with tier assignments
- `backend/tests/coverage_reports/metrics/high_impact_files.json` — 49 files, >200 lines and <30% coverage (previous run)
- `backend/tests/coverage_reports/metrics/business_impact_scores.json` — 196KB business impact tier mapping (authoritative impact tiers)
- `backend/tests/coverage_reports/metrics/coverage_266_final.json` — Most recent full-coverage snapshot (17.13%, 691 files)
- `backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json` — Historical trend data for comparison

### Phase dependencies
- `.planning/phases/291-frontend-test-suite-fixes/291-CONTEXT.md` — Phase 291 decisions (frontend test infrastructure, fix patterns, must complete first)
- `.planning/STATE.md` §"Accumulated Context" — v11.0 strategy decisions (70% pragmatic target, wave-based approach, high-impact prioritization)
- `.planning/REQUIREMENTS.md` — COV-B-01, COV-B-05, COV-F-01, COV-F-05 requirements text

### Project-level guidance
- `./CLAUDE.md` — Project architecture, coding standards, test patterns
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`prioritize_high_impact_files.py`** — Proven ranking formula with business impact weighting. Update input coverage data, run as-is.
- **`business_impact_scorer.py`** — Authoritative business impact tier assignments. Already maps every backend file to Critical/High/Medium/Low.
- **`coverage_trend_tracker.py`** — Snapshot-based trend tracking. Can record Phase 292 baseline as a trend data point.
- **`generate_coverage_dashboard.py`** — HTML dashboards. Can produce human-readable baseline visualization.
- **`MEASUREMENT_METHODOLOGY.md`** — Official measurement procedure. No new methodology needed — follow this doc.

### Established Patterns
- **Coverage measurement**: `cd backend && pytest tests/ --cov=core --cov=api --cov=tools --cov-report=json:tests/coverage_reports/metrics/coverage.json`
- **Prioritization scoring**: `priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)` where impact_score comes from `business_impact_scores.json`
- **Baseline reporting**: JSON snapshot + Markdown analysis report pair, stored in `coverage_reports/metrics/` and `coverage_reports/` respectively

### Integration Points
- **Phase 291 output**: Frontend test pass rate (must be 100% before frontend baseline measurement)
- **Phases 293-295 input**: High-impact file lists (JSON format), baseline coverage snapshots
- **Existing coverage_reports/metrics/ directory**: New baseline snapshots go here alongside historical data
</code_context>

<specifics>
## Specific Ideas

- The measurement command must target production code only — `core/`, `api/`, `tools/` — as documented in MEASUREMENT_METHODOLOGY.md
- The coverage.json output must include both `executed_lines` arrays and `summary` dicts per file for downstream parsing
- Frontend baseline measurement must use the same `COVERAGE_PHASE=phase_1` configuration that QE gates use (70% threshold)
- High-impact list must be sorted by priority_score descending within each tier
- Claude's discretion on whether to create a new Phase 292 measurement script or modify existing scripts — prefer wrapping for auditability
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 292-coverage-baselines-prioritization*
*Context gathered: 2026-04-24*
