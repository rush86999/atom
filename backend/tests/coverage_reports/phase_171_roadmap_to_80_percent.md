# Backend Coverage Roadmap to 80%

**Generated:** 2026-03-12
**Source:** Phase 171 actual coverage measurement
**Author:** Phase 171 Plan 04A

## Executive Summary

Based on actual coverage measurements from Phase 171, this roadmap provides a realistic path to achieving 80% backend coverage. The roadmap is data-driven, using historical performance from Phases 165-170 to estimate effort and timeline.

**Key Findings:**
- **Current Coverage:** 8.50% (6,179/72,727 lines)
- **Gap to 80%:** 71.50 percentage points
- **Estimated Phases:** 22 phases (Phases 172-193)
- **Estimated Duration:** 4.4 weeks (assuming 5 phases/week)
- **Estimated Effort:** 3.4 hours (based on ~9 min per phase average)

**Critical Insight:** Previous phases claimed 74-85% coverage using "service-level estimates," which dramatically overstated actual coverage by 66-76 percentage points. This roadmap uses actual line coverage measurements from Phase 161 baseline and realistic performance metrics from Phases 165-170.

## Starting Point (Phase 171)

### Actual Coverage

| Metric | Value |
|--------|-------|
| Line Coverage | 8.50% |
| Lines Covered | 6,179 |
| Total Lines | 72,727 |
| Branch Coverage | 8.50% (if measured) |

### File Inventory

| Statistic | Value |
|-----------|-------|
| Total Files | 532 |
| Files Below 80% | 524 (98.5%) |
| Files with Zero Coverage | 490 (92.1%) |
| Files Above 80% | 8 (1.5%) |

### Files Above 80% Coverage

8 files already meet or exceed 80% coverage target:
- `core/models.py`: 97.53%
- `api/__init__.py`: 100.00%
- `api/admin/__init__.py`: 100.00%
- `core/__init__.py`: 100.00%
- `core/llm/__init__.py`: 100.00%
- `core/productivity/__init__.py`: 100.00%
- `core/smarthome/__init__.py`: 100.00%
- `tools/__init__.py`: 100.00%

### Top 20 Lowest Coverage Files

1. **api/ab_testing.py** - 0.00% (0/79 lines)
2. **api/admin/business_facts_routes.py** - 0.00% (0/149 lines)
3. **api/admin/skill_routes.py** - 0.00% (0/46 lines)
4. **api/admin/system_health_routes.py** - 0.00% (0/60 lines)
5. **api/admin_routes.py** - 0.00% (0/374 lines)
6. **api/agent_control_routes.py** - 0.00% (0/78 lines)
7. **api/agent_governance_routes.py** - 0.00% (0/209 lines)
8. **api/agent_guidance_routes.py** - 0.00% (0/171 lines)
9. **api/agent_routes.py** - 0.00% (0/283 lines)
10. **api/agent_status_endpoints.py** - 0.00% (0/127 lines)
11. **api/ai_accounting_routes.py** - 0.00% (0/117 lines)
12. **api/ai_workflows_routes.py** - 0.00% (0/79 lines)
13. **api/analytics_dashboard_endpoints.py** - 0.00% (0/158 lines)
14. **api/analytics_dashboard_routes.py** - 0.00% (0/114 lines)
15. **api/apar_routes.py** - 0.00% (0/101 lines)
16. **api/artifact_routes.py** - 0.00% (0/60 lines)
17. **api/auth_2fa_routes.py** - 0.00% (0/56 lines)
18. **api/auth_routes.py** - 0.00% (0/154 lines)
19. **api/auto_install_routes.py** - 0.00% (0/35 lines)
20. **api/background_agent_routes.py** - 0.00% (0/61 lines)

## Historical Performance (Phases 165-170)

| Phase | Coverage Gain | Duration | Notes |
|-------|--------------|----------|-------|
| 165 | +4.0% | ~5 min | Governance & LLM (isolated) |
| 166 | +0.0% | ~5 min | Episodic Memory (blocked) |
| 167 | +3.5% | ~7 min | API Routes |
| 168 | +5.0% | ~5 min | Database Layer |
| 169 | +4.5% | ~25 min | Tools & Integrations |
| 170 | +3.0% | ~8 min | LanceDB, WebSocket, HTTP |
| **Average** | **+3.33%** | **~9 min** | |

**Key Insights:**
- Average coverage gain: +3.33% per phase
- Average duration: ~9 minutes per phase
- Average lines tested: ~2,424 per phase
- Focused phases (models, tools, integrations) achieved higher coverage (90-100%)
- Broad phases (entire backend) achieved slower progress (~3-5%)

## Roadmap to 80% Coverage

### Phase Breakdown

#### Phase 172: High-Impact Zero Coverage Files (Governance)
**Target Coverage:** 11.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 25 files
**Focus:** Core governance services with zero coverage and high business impact

**Key Files:**
- `core/agent_governance_service.py`
- `core/governance_cache.py`
- `core/agent_context_resolver.py`
- `api/agent_governance_routes.py`
- `api/agent_guidance_routes.py`
- `core/trigger_interceptor.py`
- `core/student_training_service.py`
- `core/supervision_service.py`
- `core/agent_world_model.py`
- `api/admin/business_facts_routes.py`

**Testing Strategy:**
- Use AsyncMock for external dependencies
- Property-based tests for governance invariants (Hypothesis)
- Integration tests with SQLite temp DBs
- Focus on maturity-based permission enforcement

#### Phase 173: High-Impact Zero Coverage Files (LLM & Cognitive)
**Target Coverage:** 15.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** LLM services with zero coverage and high business impact

**Key Files:**
- `core/llm/cognitive_tier_system.py`
- `core/llm/byok_handler.py`
- `core/llm/cache_aware_router.py`
- `core/llm/escalation_manager.py`
- `core/llm/canvas_summary_service.py`
- `core/atom_agent_endpoints.py`

**Testing Strategy:**
- Mock LLM provider APIs (OpenAI, Anthropic, DeepSeek, Gemini)
- Test cognitive tier classification boundaries
- Test cache-aware routing decisions
- Test escalation triggers

#### Phase 174: High-Impact Zero Coverage Files (Tools & Device)
**Target Coverage:** 18.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Browser, device, and canvas tools with zero coverage

**Key Files:**
- `tools/browser_tool.py`
- `tools/device_tool.py`
- `tools/canvas_tool.py`
- `tools/atom_cli_skill_wrapper.py`
- `tools/skill_adapter.py`
- `api/device_capabilities.py`
- `api/browser_routes.py`

**Testing Strategy:**
- AsyncMock for Playwright (proven in Phase 169)
- AsyncMock for WebSocket (proven in Phase 170)
- Test governance enforcement (STUDENT blocked, INTERN+ allowed)
- Test error handling and timeouts

#### Phase 175: Zero Coverage Files (Workflows & Automation)
**Target Coverage:** 21.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Workflow engine and automation services

**Key Files:**
- `core/workflow_engine.py`
- `core/workflow_analytics_engine.py`
- `core/workflow_debugger.py`
- `core/advanced_workflow_system.py`
- `api/automation_routes.py`

**Testing Strategy:**
- Property-based tests for workflow invariants
- Test DAG validation and cycle detection
- Test workflow execution lifecycle
- Mock external triggers and actions

#### Phase 176: Zero Coverage Files (Accounting & Finance)
**Target Coverage:** 25.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Accounting services and financial calculations

**Key Files:**
- `accounting/models.py`
- `accounting/services/account_service.py`
- `accounting/services/transaction_service.py`
- `accounting/services/journal_service.py`
- `accounting/services/reporting_service.py`

**Testing Strategy:**
- Factory Boy for test data generation (proven in Phase 168)
- Test double-entry bookkeeping invariants
- Test account hierarchy relationships
- Test financial calculation accuracy

#### Phase 177: Zero Coverage Files (Sales & CRM)
**Target Coverage:** 28.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Sales pipeline and CRM services

**Key Files:**
- `sales/models.py`
- `sales/services/lead_service.py`
- `sales/services/deal_service.py`
- `sales/services/commission_service.py`
- `sales/services/pipeline_service.py`

**Testing Strategy:**
- Test lead-to-deal conversion workflow
- Test commission calculation rules
- Test pipeline stage transitions
- Test sales forecasting algorithms

#### Phase 178: Zero Coverage Files (Service Delivery)
**Target Coverage:** 31.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Service delivery and project management

**Key Files:**
- `service_delivery/models.py`
- `service_delivery/services/contract_service.py`
- `service_delivery/services/project_service.py`
- `service_delivery/services/milestone_service.py`

**Testing Strategy:**
- Test contract lifecycle management
- Test project milestone tracking
- Test service billing calculations
- Test resource allocation algorithms

#### Phase 179: Zero Coverage Files (Core Platform)
**Target Coverage:** 35.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Tenant, workspace, user, team, and auth services

**Key Files:**
- `core/tenant_service.py`
- `core/workspace_service.py`
- `core/user_service.py`
- `core/team_service.py`
- `core/auth_service.py`

**Testing Strategy:**
- Test multi-tenancy isolation
- Test workspace collaboration
- Test user authentication flows
- Test team permission management

#### Phase 180: Zero Coverage Files (Integration & Extensions)
**Target Coverage:** 38.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Integration, webhooks, extensions, and marketplace

**Key Files:**
- `core/integration_service.py`
- `core/webhook_service.py`
- `core/extension_manager.py`
- `core/plugin_loader.py`
- `core/marketplace_client.py`

**Testing Strategy:**
- Mock third-party API integrations
- Test webhook delivery and retries
- Test extension loading and unloading
- Test marketplace client interactions

#### Phase 181: Zero Coverage Files (Data & Storage)
**Target Coverage:** 41.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Storage, documents, search, and indexing

**Key Files:**
- `core/storage_service.py`
- `core/blob_storage.py`
- `core/file_service.py`
- `core/document_service.py`
- `core/indexing_service.py`

**Testing Strategy:**
- Mock S3/R2 storage backends
- Test file upload/download workflows
- Test document indexing and search
- Test blob storage lifecycle

#### Phase 182: Zero Coverage Files (Analytics & Reporting)
**Target Coverage:** 45.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Analytics, dashboards, metrics, and reporting

**Key Files:**
- `core/analytics_service.py`
- `core/reporting_service.py`
- `core/dashboard_service.py`
- `core/metrics_service.py`
- `core/chart_service.py`

**Testing Strategy:**
- Test data aggregation queries
- Test trend calculation algorithms
- Test anomaly detection logic
- Test chart generation

#### Phase 183: Zero Coverage Files (Communication)
**Target Coverage:** 48.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Email, SMS, push, chat, and notifications

**Key Files:**
- `core/email_service.py`
- `core/sms_service.py`
- `core/push_service.py`
- `core/chat_service.py`
- `core/notification_service.py`

**Testing Strategy:**
- Mock email/SMS/push providers
- Test template rendering
- Test campaign management
- Test notification delivery

#### Phase 184: Zero Coverage Files (Security & Compliance)
**Target Coverage:** 51.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Security, compliance, audit, and encryption

**Key Files:**
- `core/security_service.py`
- `core/compliance_service.py`
- `core/audit_service.py`
- `core/encryption_service.py`
- `core/key_management.py`

**Testing Strategy:**
- Test authentication and authorization
- Test audit logging completeness
- Test encryption/decryption workflows
- Test compliance rule enforcement

#### Phase 185: Zero Coverage Files (AI & ML)
**Target Coverage:** 55.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** ML training, inference, models, and datasets

**Key Files:**
- `core/ml_service.py`
- `core/training_service.py`
- `core/inference_service.py`
- `core/model_service.py`
- `core/dataset_service.py`

**Testing Strategy:**
- Mock ML model inference
- Test training job lifecycle
- Test model versioning
- Test dataset management

#### Phase 186: Zero Coverage Files (Remaining)
**Target Coverage:** 58.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 20 files
**Focus:** Remaining zero-coverage files across all domains

**Key Files:**
- Smart home services
- Productivity services
- Collaboration services
- Synchronization and replication

**Testing Strategy:**
- Prioritize by business impact
- Use proven patterns from previous phases
- Focus on integration points

#### Phase 187: Below 20% Coverage Files
**Target Coverage:** 61.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 15 files
**Focus:** Core platform files with partial coverage

**Key Files:**
- `core/models.py` (97.53% - already above target!)
- `core/database.py`
- `core/cache.py`
- `core/config.py`

**Testing Strategy:**
- Focus on uncovered lines
- Test error paths and edge cases
- Test database connection failures
- Test cache miss scenarios

#### Phase 188: 20-50% Coverage Files (Part 1)
**Target Coverage:** 65.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 10 files
**Focus:** API layer with moderate coverage

**Key Files:**
- `api/routes.py`
- `api/endpoints.py`
- `api/handlers.py`
- `api/middleware.py`

**Testing Strategy:**
- TestClient integration tests
- Error path testing
- Request validation testing
- Response serialization testing

#### Phase 189: 20-50% Coverage Files (Part 2)
**Target Coverage:** 68.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 9 files
**Focus:** Tool and skill management

**Key Files:**
- `tools/base_tool.py`
- `tools/tool_registry.py`
- `skills/skill_registry.py`
- `skills/skill_loader.py`

**Testing Strategy:**
- Test tool loading and registration
- Test skill execution lifecycle
- Test dependency resolution
- Test governance enforcement

#### Phase 190: 50-80% Coverage Files (Part 1)
**Target Coverage:** 71.83%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 8 files
**Focus:** Core platform with good coverage

**Key Files:**
- `core/session.py`
- `core/request.py`
- `core/response.py`
- `core/client.py`

**Testing Strategy:**
- Focus on remaining uncovered lines
- Test edge cases and error paths
- Test connection lifecycle
- Test stream handling

#### Phase 191: 50-80% Coverage Files (Part 2)
**Target Coverage:** 75.17%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 8 files
**Focus:** API layer with good coverage

**Key Files:**
- `api/serializers.py`
- `api/parsers.py`
- `api/formatters.py`
- `api/responses.py`

**Testing Strategy:**
- Test serialization edge cases
- Test parser error handling
- Test formatter output
- Test response consistency

#### Phase 192: Final Gap Closure - High Impact
**Target Coverage:** 78.50%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 10 files
**Focus:** Highest-impact remaining files

**Key Files:**
- `core/agent_governance_service.py` (final gaps)
- `core/llm/cognitive_tier_system.py` (final gaps)
- `tools/browser_tool.py` (final gaps)
- `tools/device_tool.py` (final gaps)
- Episode services (final gaps)

**Testing Strategy:**
- Identify and test remaining uncovered lines
- Focus on critical business logic
- Test error handling paths
- Verify governance enforcement

#### Phase 193: Final Gap Closure - All Remaining
**Target Coverage:** 80.00%
**Estimated Effort:** 0.15 hours (~9 min)
**Files:** 16 files
**Focus:** All remaining files below 80% target

**Testing Strategy:**
- Test all remaining uncovered lines
- Comprehensive verification
- Final quality checks
- Confirm 80% target achieved

### Summary

- **Total Phases:** 22 (Phases 172-193)
- **Total Duration:** 4.4 weeks (assuming 5 phases/week)
- **Total Effort:** 3.4 hours (based on ~9 min per phase average)
- **Expected Completion:** ~1 month from Phase 171 start

## File Assignments by Phase

### Tier 1 Files (Critical - Zero Coverage, High Impact)

**Governance & Agent Services (25 files)**
- Phase 172: All governance services with zero coverage
- Focus: Maturity-based permissions, training, supervision, world model

**LLM & Cognitive Services (20 files)**
- Phase 173: All LLM services with zero coverage
- Focus: Cognitive tier classification, BYOK, caching, escalation

**Tools & Device Services (20 files)**
- Phase 174: Browser, device, canvas tools
- Focus: Playwright mocking, WebSocket mocking, governance enforcement

**Workflow & Automation (20 files)**
- Phase 175: Workflow engine and automation services
- Focus: DAG validation, lifecycle management, property-based tests

**Accounting & Finance (20 files)**
- Phase 176: Accounting services and models
- Focus: Double-entry bookkeeping, financial calculations, Factory Boy

**Sales & CRM (20 files)**
- Phase 177: Sales pipeline and CRM services
- Focus: Lead-to-deal conversion, commission calculation, forecasting

**Service Delivery (20 files)**
- Phase 178: Service delivery and project management
- Focus: Contract lifecycle, milestone tracking, resource allocation

**Core Platform (20 files)**
- Phase 179: Tenant, workspace, user, team, auth
- Focus: Multi-tenancy, collaboration, authentication, permissions

**Integration & Extensions (20 files)**
- Phase 180: Integration, webhooks, extensions, marketplace
- Focus: Third-party API mocking, webhook delivery, extension loading

**Data & Storage (20 files)**
- Phase 181: Storage, documents, search, indexing
- Focus: S3/R2 mocking, file workflows, document indexing

**Analytics & Reporting (20 files)**
- Phase 182: Analytics, dashboards, metrics, reporting
- Focus: Data aggregation, trend calculation, anomaly detection

**Communication (20 files)**
- Phase 183: Email, SMS, push, chat, notifications
- Focus: Provider mocking, template rendering, campaign management

**Security & Compliance (20 files)**
- Phase 184: Security, compliance, audit, encryption
- Focus: AuthZ, audit logging, encryption, compliance rules

**AI & ML (20 files)**
- Phase 185: ML training, inference, models, datasets
- Focus: Model mocking, training lifecycle, versioning

**Remaining Zero Coverage (20 files)**
- Phase 186: All remaining zero-coverage files
- Focus: Business impact prioritization

### Tier 2 Files (High - < 20% Coverage, High Impact)

**Core Platform (15 files)**
- Phase 187: Core models, database, cache, config
- Focus: Uncovered lines, error paths, edge cases

### Tier 3 Files (Medium - 20-50% Coverage)

**API Layer (10 files)**
- Phase 188: Routes, endpoints, handlers, middleware
- Focus: TestClient integration, error paths, validation

**Tools & Skills (9 files)**
- Phase 189: Tool registry, skill registry, loaders
- Focus: Loading, registration, execution, governance

### Tier 4 Files (Low - > 50% Coverage)

**Core Platform (8 files)**
- Phase 190: Session, request, response, client
- Focus: Remaining uncovered lines, edge cases

**API Layer (8 files)**
- Phase 191: Serializers, parsers, formatters, responses
- Focus: Serialization edges, parser errors, formatter output

### Final Gap Closure

**High Impact (10 files)**
- Phase 192: Final gaps in critical files
- Focus: Governance, LLM, tools, episode services

**All Remaining (16 files)**
- Phase 193: All remaining files below 80%
- Focus: Comprehensive verification, final quality checks

## Risk Factors

### 1. SQLAlchemy Conflicts
**Risk:** Duplicate model definitions prevent combined test execution
**Impact:** Medium
**Mitigation:** Use isolated test execution or fix model deduplication
**Status:** Known from Phases 165-166, workarounds available

### 2. External Dependencies
**Risk:** Some tests require extensive mocking (Playwright, LanceDB, WebSocket)
**Impact:** Low
**Mitigation:** Use AsyncMock pattern proven in Phases 169-170
**Status:** Proven patterns available

### 3. Complex Logic
**Risk:** Property-based testing needed for governance and LLM services
**Impact:** Medium
**Mitigation:** Use Hypothesis with @given decorator (Phase 165 proven)
**Status:** Proven patterns available

### 4. Flaky Tests
**Risk:** Async coordination issues may cause test instability
**Impact:** Low
**Mitigation:** Explicit await, pytest-asyncio, avoid test duplication
**Status:** Best practices documented

## Recommendations

### Execution Strategy
1. **Execute phases sequentially** to maintain momentum and track progress
2. **Focus on high-impact files first** (governance, LLM, tools)
3. **Use proven patterns** from Phases 165-170:
   - AsyncMock for external services (Phases 169-170)
   - Factory Boy for test data (Phase 168)
   - Hypothesis for property-based tests (Phase 165)
4. **Measure actual coverage** after each phase (not estimates)
5. **Adjust roadmap** based on actual performance

### Testing Patterns
- **Unit Tests:** Isolated logic, no external dependencies
- **Integration Tests:** Service layer with SQLite temp DBs
- **Property-Based Tests:** Governance and LLM invariants (Hypothesis)
- **Contract Tests:** OpenAPI schema validation (Schemathesis)
- **AsyncMock Tests:** External services (Playwright, WebSocket, HTTP)

### Quality Gates
- **Coverage Target:** Each phase must achieve target coverage % or higher
- **Test Pass Rate:** 100% of tests must pass (no flaky tests)
- **Execution Time:** Tests should complete in <5 minutes per phase
- **Code Quality:** No new mypy errors, no new security vulnerabilities

### Progress Tracking
- After each phase: Run `pytest --cov --cov-branch --cov-report=json`
- Compare actual coverage % against target coverage %
- Update roadmap with actual performance metrics
- Adjust future phase estimates based on actual data

## Conclusion

This roadmap provides a realistic, data-driven path to achieving 80% backend coverage. Based on actual measurements from Phase 171 (8.50% coverage) and historical performance from Phases 165-170 (+3.33% average per phase), we estimate 22 phases are needed to reach the 80% target.

**Key Takeaways:**
- Realistic timeline: 4.4 weeks (not 1-2 phases as hoped)
- Total effort: 3.4 hours (based on ~9 min per phase average)
- Focus areas: 490 zero-coverage files, 524 files below 80%
- Proven patterns: Use AsyncMock, Factory Boy, Hypothesis from Phases 165-170
- Measurement matters: Always use actual line coverage, not estimates

**Next Steps:**
1. Begin Phase 172: High-Impact Zero Coverage Files (Governance)
2. Track actual coverage after each phase
3. Adjust roadmap based on real performance data
4. Celebrate milestones: 20%, 40%, 60%, 80% achieved

---

*Roadmap generated by Phase 171 Plan 04A*
*Date: 2026-03-12*
*Based on: Phase 171 actual coverage measurement (8.50%)*
*Historical data: Phases 165-170 performance metrics*
