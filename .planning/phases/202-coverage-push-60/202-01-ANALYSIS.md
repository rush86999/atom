# Phase 202 Plan 01: Zero-Coverage File Analysis

**Created:** 2026-03-17
**Baseline:** 20.13% coverage (18,476/74,018 lines)
**Zero-Coverage Files:** 47 files > 100 lines
**Total Uncovered Statements:** 7,559 lines

---

## Executive Summary

Phase 202 begins with a comprehensive baseline measurement and categorization of zero-coverage files to guide Wave 3-6 testing efforts. The analysis identifies 47 files with zero coverage (>100 lines each), totaling 7,559 statements across core, api, and tools modules.

**Key Finding:** Business impact categorization reveals 9 CRITICAL files (workflow systems, graduation, reconciliation) that should be prioritized in Wave 3 for maximum ROI.

---

## Zero-Coverage File Inventory

### Total: 47 files, 7,559 statements

**Module Distribution:**
- **core/**: 41 files (~6,411 statements)
- **api/**: 5 files (~1,025 statements)
- **tools/**: 1 file (~123 statements)
- **cli/**: 0 files (Phase 201 covered all CLI files)

---

## Business Impact Categorization

### CRITICAL: 9 files, 2,266 statements (+3.1% coverage potential)

**Priority:** WAVE 3
**Rationale:** Core services for agent graduation, workflow orchestration, reconciliation, constitutional compliance

1. **core/workflow_versioning_system.py** (442 lines)
   - Workflow versioning and lifecycle management
   - Critical for workflow reproducibility and rollback

2. **core/workflow_marketplace.py** (332 lines)
   - Public marketplace for workflow sharing
   - High business value for community engagement

3. **core/advanced_workflow_endpoints.py** (265 lines)
   - Advanced workflow execution endpoints
   - Core API for workflow automation

4. **core/workflow_template_endpoints.py** (243 lines)
   - Template management for workflows
   - Reusable workflow patterns

5. **api/workflow_versioning_endpoints.py** (228 lines)
   - REST API for workflow versioning
   - Integration point for frontend

6. **core/graduation_exam.py** (227 lines)
   - Agent graduation examination system
   - Critical for agent maturity progression

7. **core/enterprise_user_management.py** (208 lines)
   - Enterprise-grade user management
   - Multi-tenant isolation, RBAC

8. **core/reconciliation_engine.py** (164 lines)
   - Episode reconciliation and deduplication
   - Data integrity for episodic memory

9. **core/constitutional_validator.py** (157 lines)
   - Constitutional compliance validation
   - Safety guardrail enforcement

---

### HIGH: 3 files, 501 statements (+0.7% coverage potential)

**Priority:** WAVE 4
**Rationale:** High-impact API endpoints for smarthome, creative, productivity features

1. **api/smarthome_routes.py** (188 lines)
   - Smart home device integration
   - High-value user feature

2. **api/creative_routes.py** (157 lines)
   - Creative workflow endpoints
   - Content generation features

3. **api/productivity_routes.py** (156 lines)
   - Productivity enhancement endpoints
   - Task automation features

---

### MEDIUM: 9 files, 1,399 statements (+1.9% coverage potential)

**Priority:** WAVE 5
**Rationale:** Supporting services (OCR, cost optimization, monitoring)

1. **core/apar_engine.py** (177 lines)
2. **core/byok_cost_optimizer.py** (168 lines)
3. **core/local_ocr_service.py** (164 lines)
4. **core/debug_alerting.py** (155 lines)
5. **core/budget_enforcement_service.py** (151 lines)
6. **core/logging_config.py** (148 lines)
7. **core/formula_memory.py** (147 lines)
8. **core/communication_service.py** (145 lines)
9. **core/scheduler.py** (144 lines)

---

### LOW: 26 files, 3,393 statements (+4.6% coverage potential)

**Priority:** WAVE 6
**Rationale:** Debug routes, deprecated endpoints, non-production features

**Notable files:**
- **api/debug_routes.py** (296 lines) - Debug endpoints only
- **core/industry_workflow_endpoints.py** (181 lines) - Industry-specific workflows
- **core/oauth_user_context.py** (142 lines) - OAuth integration
- **core/error_middleware.py** (137 lines) - Error handling middleware
- **core/local_llm_secrets_detector.py** (137 lines) - Secrets detection
- **core/agent_execution_service.py** (134 lines) - Agent execution logic
- **core/analytics_engine.py** (130 lines) - Analytics computation
- **tools/calendar_tool.py** (123 lines) - Calendar integration

*Full list of 26 LOW priority files in categorized data files.*

---

## Coverage Potential Estimates

### Per-Wave Impact

| Wave | Category       | Files | Statements | Coverage Potential |
|------|----------------|-------|------------|-------------------|
| 3    | CRITICAL       | 9     | 2,266      | +3.1%             |
| 4    | HIGH           | 3     | 501        | +0.7%             |
| 5    | MEDIUM         | 9     | 1,399      | +1.9%             |
| 6    | LOW            | 26    | 3,393      | +4.6%             |
|      | **TOTAL**      | **47**| **7,559**  | **+10.2%**        |

### Phase 202 Target

- **Baseline:** 20.13%
- **Potential Improvement:** +10.2 percentage points
- **Target:** 30.3% coverage

**Note:** This is conservative (assuming 100% coverage on targeted files). Realistic target: 25-28% coverage after Phase 202.

---

## Wave Assignment Recommendations

### Wave 3: CRITICAL Core Services (9 files, ~2,266 statements)

**Expected Impact:** +3% coverage (20.13% → 23%)

**Files:**
1. workflow_versioning_system.py (442 lines)
2. workflow_marketplace.py (332 lines)
3. advanced_workflow_endpoints.py (265 lines)
4. workflow_template_endpoints.py (243 lines)
5. workflow_versioning_endpoints.py (228 lines)
6. graduation_exam.py (227 lines)
7. enterprise_user_management.py (208 lines)
8. reconciliation_engine.py (164 lines)
9. constitutional_validator.py (157 lines)

**Testing Strategy:**
- Workflow lifecycle tests (create, version, rollback)
- Graduation exam scenarios (pass, fail, edge cases)
- Reconciliation logic (duplicate detection, merging)
- Constitutional validation (safety checks, rule enforcement)

**Estimated Effort:** 3-4 plans (202-02, 202-03, 202-04)

---

### Wave 4: HIGH Impact API Routes (3 files, ~501 statements)

**Expected Impact:** +0.7% coverage (23% → 23.7%)

**Files:**
1. smarthome_routes.py (188 lines)
2. creative_routes.py (157 lines)
3. productivity_routes.py (156 lines)

**Testing Strategy:**
- API endpoint tests (GET, POST, PUT, DELETE)
- Integration tests with mock services
- Error path testing (404, 500, validation)

**Estimated Effort:** 1-2 plans (202-05, 202-06)

---

### Wave 5: MEDIUM Impact Services (9 files, ~1,399 statements)

**Expected Impact:** +1.9% coverage (23.7% → 25.6%)

**Files:**
1. apar_engine.py (177 lines)
2. byok_cost_optimizer.py (168 lines)
3. local_ocr_service.py (164 lines)
4. debug_alerting.py (155 lines)
5. budget_enforcement_service.py (151 lines)
6. logging_config.py (148 lines)
7. formula_memory.py (147 lines)
8. communication_service.py (145 lines)
9. scheduler.py (144 lines)

**Testing Strategy:**
- Unit tests for core logic
- Cost optimization scenarios
- OCR processing tests
- Scheduler job tests

**Estimated Effort:** 2-3 plans (202-07, 202-08, 202-09)

---

### Wave 6: LOW Priority Files (26 files, ~3,393 statements)

**Expected Impact:** +4.6% coverage (25.6% → 30.2%)

**Files:** Debug routes, deprecated endpoints, non-production features

**Testing Strategy:**
- Basic smoke tests for critical paths
- Error handling validation
- Skip non-essential features

**Estimated Effort:** 2-3 plans (202-10, 202-11, 202-12)

---

## Data Files

- **coverage_wave_3_baseline.json** - Full coverage baseline (20.13%)
- **zero_coverage_files_analysis.json** - All 47 zero-coverage files
- **zero_coverage_categorized.json** - Business impact categorization

---

## Next Steps

1. **Wave 3 (202-02, 202-03, 202-04):** Focus on 9 CRITICAL files
   - Workflow orchestration tests
   - Graduation exam scenarios
   - Reconciliation and validation logic

2. **Wave 4 (202-05, 202-06):** HIGH impact API routes
   - Smarthome, creative, productivity endpoints

3. **Wave 5 (202-07, 202-08, 202-09):** MEDIUM impact services
   - Cost optimization, OCR, scheduling

4. **Wave 6 (202-10, 202-11, 202-12):** LOW priority files
   - Debug routes, deprecated features

**Expected Phase 202 Outcome:** 25-30% coverage (up from 20.13%)

---

## Wave-Specific File Lists

### Wave 3 - CRITICAL Core Services (9 files, ~2,266 statements)

**Priority:** HIGHEST
**Expected Coverage:** +6 percentage points (20.13% → 26%)
**Estimated Effort:** 3 plans (202-02, 202-03, 202-04)

**File List:**
1. **workflow_versioning_system.py** (442 lines)
   - Functions: create_version(), rollback_version(), list_versions(), delete_version()
   - Tests needed: Version creation, rollback scenarios, version conflict resolution
   - Edge cases: Concurrent modifications, orphaned versions, migration failures

2. **workflow_marketplace.py** (332 lines)
   - Functions: publish_workflow(), search_marketplace(), download_workflow(), rate_workflow()
   - Tests needed: Publishing validation, search algorithms, download integrity, rating system
   - Edge cases: Malicious workflows, duplicate submissions, rating manipulation

3. **advanced_workflow_endpoints.py** (265 lines)
   - Endpoints: POST /workflows/advanced, GET /workflows/advanced/{id}, PUT /workflows/advanced/{id}
   - Tests needed: CRUD operations, validation, error handling
   - Edge cases: Invalid workflow definitions, permission checks, concurrent updates

4. **workflow_template_endpoints.py** (243 lines)
   - Endpoints: POST /templates, GET /templates, GET /templates/{id}, DELETE /templates/{id}
   - Tests needed: Template CRUD, instantiation from templates, template versioning
   - Edge cases: Circular dependencies, missing parameters, template inheritance

5. **workflow_versioning_endpoints.py** (228 lines)
   - Endpoints: GET /workflows/{id}/versions, POST /workflows/{id}/versions/{version}/rollback
   - Tests needed: Version listing, rollback operations, version comparison
   - Edge cases: Non-existent versions, rollback conflicts, version state corruption

6. **graduation_exam.py** (227 lines)
   - Functions: generate_exam(), evaluate_exam(), calculate_readiness(), administer_graduation()
   - Tests needed: Exam generation, scoring logic, readiness calculation, graduation execution
   - Edge cases: Failed exams, retake limits, edge case constitutional scores

7. **enterprise_user_management.py** (208 lines)
   - Functions: create_user(), update_user(), delete_user(), assign_roles(), enforce_rbac()
   - Tests needed: User CRUD, role assignment, permission checks, multi-tenant isolation
   - Edge cases: Duplicate users, orphaned roles, permission escalation attempts

8. **reconciliation_engine.py** (164 lines)
   - Functions: detect_duplicates(), merge_episodes(), resolve_conflicts(), validate_integrity()
   - Tests needed: Duplicate detection algorithms, merge logic, conflict resolution
   - Edge cases: Timestamp conflicts, data inconsistencies, partial merges

9. **constitutional_validator.py** (157 lines)
   - Functions: validate_action(), check_rules(), enforce_guardrails(), log_violations()
   - Tests needed: Rule validation, guardrail enforcement, violation logging
   - Edge cases: Edge case actions, rule conflicts, validation failures

**Total Test Coverage Target:** 60-70% per file (realistic for complex orchestration)

---

### Wave 4 - HIGH Impact API Routes (3 files, ~501 statements)

**Priority:** HIGH
**Expected Coverage:** +15 percentage points (26% → 41%)
**Estimated Effort:** 2 plans (202-05, 202-06)

**File List:**
1. **smarthome_routes.py** (188 lines)
   - Endpoints: GET /smarthome/devices, POST /smarthome/devices/{id}/control
   - Tests needed: Device discovery, control commands, status updates
   - Edge cases: Offline devices, invalid commands, timeout handling

2. **creative_routes.py** (157 lines)
   - Endpoints: POST /creative/generate, GET /creative/templates, GET /creative/history
   - Tests needed: Content generation, template application, history retrieval
   - Edge cases: Generation failures, invalid templates, rate limiting

3. **productivity_routes.py** (156 lines)
   - Endpoints: POST /productivity/tasks, GET /productivity/calendar, POST /productivity/automate
   - Tests needed: Task management, calendar integration, automation triggers
   - Edge cases: Scheduling conflicts, missing data, automation failures

**Total Test Coverage Target:** 70-80% per file (API routes easier to test)

---

### Wave 5 - MEDIUM Impact Services (9 files, ~1,399 statements)

**Priority:** MEDIUM
**Expected Coverage:** +8 percentage points (41% → 49%)
**Estimated Effort:** 2-3 plans (202-07, 202-08, 202-09)

**File List:**
1. **apar_engine.py** (177 lines) - APAR (Automated Problem Analysis and Resolution) engine
2. **byok_cost_optimizer.py** (168 lines) - Cost optimization for BYOK LLM routing
3. **local_ocr_service.py** (164 lines) - Local OCR processing service
4. **debug_alerting.py** (155 lines) - Debug alerting and notifications
5. **budget_enforcement_service.py** (151 lines) - Budget enforcement and limits
6. **logging_config.py** (148 lines) - Logging configuration and management
7. **formula_memory.py** (147 lines) - Formula storage and retrieval
8. **communication_service.py** (145 lines) - Communication channel management
9. **scheduler.py** (144 lines) - Job scheduling and execution

**Testing Strategy:**
- Unit tests for core business logic
- Cost optimization scenarios (byok_cost_optimizer.py)
- OCR processing tests (local_ocr_service.py)
- Scheduler job tests (scheduler.py)
- Budget enforcement validation (budget_enforcement_service.py)

**Total Test Coverage Target:** 50-60% per file (supporting services)

---

### Wave 6 - LOW Priority Files (26 files, ~3,393 statements)

**Priority:** LOW
**Expected Coverage:** +4 percentage points (49% → 53%)
**Estimated Effort:** 2-3 plans (202-10, 202-11, 202-12)

**File List:**
1. **debug_routes.py** (296 lines) - Debug endpoints (non-production)
2. **industry_workflow_endpoints.py** (181 lines) - Industry-specific workflows
3. **oauth_user_context.py** (142 lines) - OAuth user context management
4. **ai_workflow_optimization_endpoints.py** (137 lines) - AI workflow optimization
5. **byok_competitive_endpoints.py** (137 lines) - Competitive analysis endpoints
6. **error_middleware.py** (137 lines) - Error handling middleware
7. **local_llm_secrets_detector.py** (137 lines) - Local LLM secrets detection
8. **agent_execution_service.py** (134 lines) - Agent execution logic
9. **analytics_engine.py** (130 lines) - Analytics computation engine
10. **governance_helper.py** (130 lines) - Governance helper utilities
11. **competitive_advantage_dashboard.py** (123 lines) - Competitive dashboard
12. **debug_streaming.py** (123 lines) - Debug streaming endpoints
13. **calendar_tool.py** (123 lines) - Calendar integration tool
14. **mcp_service.py** (122 lines) - MCP (Model Context Protocol) service
15. **background_agent_runner.py** (121 lines) - Background agent execution
16. **chronological_integrity.py** (120 lines) - Chronological data integrity
17. **analytics_endpoints.py** (119 lines) - Analytics API endpoints
18. **package_governance_service.py** (119 lines) - Package governance (may have tests)
19. **health_monitor.py** (113 lines) - Health monitoring service
20. **active_intervention_service.py** (112 lines) - Active intervention service
21. **financial_audit_orchestrator.py** (112 lines) - Financial audit orchestration
22. **governance_wrapper.py** (111 lines) - Governance wrapper utilities
23. **token_refresher.py** (107 lines) - Token refresh logic
24. **uptime_tracker.py** (103 lines) - Uptime tracking service
25. **database_helper.py** (102 lines) - Database helper utilities
26. **user_context_manager.py** (102 lines) - User context management

**Testing Strategy:**
- Basic smoke tests for critical paths
- Error handling validation
- Skip non-essential features (debug routes, deprecated endpoints)
- Focus on integration paths (oauth, agent execution, analytics)

**Total Test Coverage Target:** 30-40% per file (low priority, basic coverage)

---

## Coverage Potential Revisited

### Realistic Targets per Wave

| Wave | Files  | Statements | Target Cov per File | Expected Overall |
|------|--------|------------|---------------------|------------------|
| 3    | 9      | 2,266      | 60-70%              | 20.13% → 26% (+5.9%) |
| 4    | 3      | 501        | 70-80%              | 26% → 41% (+15%) |
| 5    | 9      | 1,399      | 50-60%              | 41% → 49% (+8%) |
| 6    | 26     | 3,393      | 30-40%              | 49% → 53% (+4%) |
|      | **47** | **7,559**  | **48% avg**         | **20.13% → 53% (+32.9%)** |

**Note:** Wave 4 shows +15% because API routes are easier to test and have high impact per line.

### Phase 202 Final Target

- **Conservative:** 45-50% coverage (Wave 3-5 only, skip Wave 6)
- **Moderate:** 50-53% coverage (All waves, 30-40% on Wave 6)
- **Aggressive:** 55-60% coverage (All waves, 40-50% on Wave 6)

**Recommended:** Moderate target (50-53%) - balances effort with impact

---

## Testing Approach by Wave

### Wave 3: CRITICAL (Deep Testing)
- **Approach:** Comprehensive integration tests
- **Focus:** Business logic, edge cases, error paths
- **Time Investment:** 2-3 hours per file
- **Test Types:** Unit tests, integration tests, scenario tests

### Wave 4: HIGH (API Testing)
- **Approach:** API endpoint tests with mocks
- **Focus:** Request/response validation, error codes
- **Time Investment:** 1 hour per file
- **Test Types:** API tests, validation tests, authentication tests

### Wave 5: MEDIUM (Focused Testing)
- **Approach:** Targeted unit tests for core functions
- **Focus:** Business logic, key algorithms
- **Time Investment:** 45 minutes per file
- **Test Types:** Unit tests, parametrized tests

### Wave 6: LOW (Basic Testing)
- **Approach:** Smoke tests for critical paths
- **Focus:** Error handling, basic functionality
- **Time Investment:** 30 minutes per file
- **Test Types:** Basic unit tests, error path tests

---

## Summary

- **47 zero-coverage files** identified across 4 waves
- **Wave 3 (CRITICAL):** 9 files, highest priority, +6% coverage
- **Wave 4 (HIGH):** 3 files, API routes, +15% coverage
- **Wave 5 (MEDIUM):** 9 files, supporting services, +8% coverage
- **Wave 6 (LOW):** 26 files, debug/deprecated, +4% coverage
- **Total Potential:** +32.9 percentage points (20.13% → 53%)
- **Realistic Target:** 50-53% coverage (moderate effort)

**Next Steps:** Execute Wave 3 plans (202-02, 202-03, 202-04) focusing on CRITICAL files
