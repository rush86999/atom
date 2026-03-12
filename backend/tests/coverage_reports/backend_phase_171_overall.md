# Backend Coverage Report - Phase 171
**Generated:** 2026-03-10T11:58:00Z
**Phase:** 171 - Gap Closure & Final Push

## Executive Summary
- **Line Coverage:** 8.50% (6,179/72,727 lines)
- **Source:** Phase 161 baseline (authoritative full-backend measurement)

## Actual vs Previous Estimates

### Discrepancy Analysis

| Source | Claimed | Actual | Gap |
|--------|---------|--------|-----|
| Phase_166 | 85.00% | 8.50% | 76.50pp |
| Phase_164 | 74.55% | 8.50% | 66.05pp |

**Key Finding:** Previous phases used "service-level estimates" which dramatically overstated actual coverage. Phase 161's comprehensive measurement of all 72,727 lines revealed the true baseline is 8.50%, not 74-85% as previously claimed.

## Coverage Gap to 80% Target
- **Current:** 8.50%
- **Target:** 80.00%
- **Gap:** 71.50 percentage points
- **Lines Needed:** 52,002

## File Statistics
- **Total Files:** 532
- **Files Below 80%:** 524
- **Files with Zero Coverage:** 490

## Files Below 80% Coverage (Top 20)

1. **api/ab_testing.py**
   - Coverage: 0.00% (0/79)
   - Missing: 79 lines

2. **api/admin/business_facts_routes.py**
   - Coverage: 0.00% (0/149)
   - Missing: 149 lines

3. **api/admin/skill_routes.py**
   - Coverage: 0.00% (0/46)
   - Missing: 46 lines

4. **api/admin/system_health_routes.py**
   - Coverage: 0.00% (0/60)
   - Missing: 60 lines

5. **api/admin_routes.py**
   - Coverage: 0.00% (0/374)
   - Missing: 374 lines

6. **api/agent_control_routes.py**
   - Coverage: 0.00% (0/78)
   - Missing: 78 lines

7. **api/agent_governance_routes.py**
   - Coverage: 0.00% (0/209)
   - Missing: 209 lines

8. **api/agent_guidance_routes.py**
   - Coverage: 0.00% (0/171)
   - Missing: 171 lines

9. **api/agent_routes.py**
   - Coverage: 0.00% (0/283)
   - Missing: 283 lines

10. **api/agent_status_endpoints.py**
   - Coverage: 0.00% (0/127)
   - Missing: 127 lines

11. **api/ai_accounting_routes.py**
   - Coverage: 0.00% (0/117)
   - Missing: 117 lines

12. **api/ai_workflows_routes.py**
   - Coverage: 0.00% (0/79)
   - Missing: 79 lines

13. **api/analytics_dashboard_endpoints.py**
   - Coverage: 0.00% (0/158)
   - Missing: 158 lines

14. **api/analytics_dashboard_routes.py**
   - Coverage: 0.00% (0/114)
   - Missing: 114 lines

15. **api/apar_routes.py**
   - Coverage: 0.00% (0/101)
   - Missing: 101 lines

16. **api/artifact_routes.py**
   - Coverage: 0.00% (0/60)
   - Missing: 60 lines

17. **api/auth_2fa_routes.py**
   - Coverage: 0.00% (0/56)
   - Missing: 56 lines

18. **api/auth_routes.py**
   - Coverage: 0.00% (0/154)
   - Missing: 154 lines

19. **api/auto_install_routes.py**
   - Coverage: 0.00% (0/35)
   - Missing: 35 lines

20. **api/background_agent_routes.py**
   - Coverage: 0.00% (0/61)
   - Missing: 61 lines


## Files Above 80% Coverage

8 files meet or exceed 80% coverage target:
- core/models.py: 97.53%
- api/__init__.py: 100.00%
- api/admin/__init__.py: 100.00%
- core/__init__.py: 100.00%
- core/llm/__init__.py: 100.00%
- core/productivity/__init__.py: 100.00%
- core/smarthome/__init__.py: 100.00%
- tools/__init__.py: 100.00%

## Realistic Roadmap to 80% Target

### Effort Calculation
- **Current Coverage:** 8.50% (6,179/72,727 lines)
- **Target Coverage:** 80.00%
- **Lines to Cover:** 52,002
- **Estimated Hours:** 1040 hours (at 50 lines/hour average)
- **Estimated Phases:** 18 phases (at 4pp/phase average)

### Phase Breakdown
Based on Phases 165-170 performance (~3-5pp per phase):

- **Phase 172:** Target 12.50% - High-impact zero-coverage files
- **Phase 173:** Target 16.50% - API routes with critical paths
- **Phase 174:** Target 20.50% - Episodic memory services
- **Phase 175:** Target 24.50% - Tools and integrations
- **Phase 176:** Target 28.50% - Continued coverage improvement
- **Phase 177:** Target 32.50% - Continued coverage improvement
- **Phase 178:** Target 36.50% - Continued coverage improvement
- **Phase 179:** Target 40.50% - Continued coverage improvement
- **Phase 180:** Target 44.50% - Continued coverage improvement
- **Phase 181:** Target 48.50% - Continued coverage improvement
- **Phase 182:** Target 52.50% - Continued coverage improvement
- **Phase 183:** Target 56.50% - Continued coverage improvement
- **Phase 184:** Target 60.50% - Continued coverage improvement
- **Phase 185:** Target 64.50% - Continued coverage improvement
- **Phase 186:** Target 68.50% - Continued coverage improvement
- **Phase 187:** Target 72.50% - Continued coverage improvement
- **Phase 188:** Target 76.50% - Continued coverage improvement
- **Phase 189:** Target 80.00% - Continued coverage improvement

### Recommended Next Phases
1. **Phase 172:** High-impact zero-coverage files (governance, LLM)
2. **Phase 173:** API routes with critical paths
3. **Phase 174:** Episodic memory services
4. **Phase 175:** Tools and integrations
5. Continue until 80% achieved