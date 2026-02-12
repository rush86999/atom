---
phase: 05-coverage-quality-validation
plan: 01b
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/unit/governance/test_proposal_service.py
  - backend/tests/unit/governance/test_agent_graduation_governance.py
  - backend/tests/unit/governance/test_agent_context_resolver.py
autonomous: true

must_haves:
  truths:
    - "Proposal service, agent graduation governance logic, and context resolver have unit tests covering happy path and error cases"
    - "Proposal service generates proposals for INTERN agents with approval workflow"
    - "Graduation service validates governance-specific graduation criteria (maturity transitions, confidence scores, permission matrix)"
    - "Context resolver provides fallback chain for agent ID resolution"
    - "Governance services achieve 80% coverage"
  artifacts:
    - path: "backend/tests/unit/governance/test_proposal_service.py"
      provides: "Unit tests for INTERN agent proposal generation and approval"
      contains: "test_class: TestProposalService"
    - path: "backend/tests/unit/governance/test_agent_graduation_governance.py"
      provides: "Unit tests for governance-specific graduation logic"
      contains: "test_class: TestAgentGraduationGovernance"
    - path: "backend/tests/unit/governance/test_agent_context_resolver.py"
      provides: "Unit tests for agent context resolution with fallback chain"
      contains: "test_class: TestAgentContextResolver"
  key_links:
    - from: "test_proposal_service.py"
      to: "core/proposal_service.py"
      via: "direct imports and mocked approval workflow"
      pattern: "from core.proposal_service import"
    - from: "test_agent_graduation_governance.py"
      to: "core/agent_graduation_service.py"
      via: "direct imports for governance logic testing"
      pattern: "from core.agent_graduation_service import"
    - from: "test_agent_context_resolver.py"
      to: "core/agent_context_resolver.py"
      via: "direct imports and mocked cache/governance service"
      pattern: "from core.agent_context_resolver import"
---

<objective>
Achieve 80% test coverage for governance services: proposal service, graduation service (governance logic), and context resolver. This is part 2 of 2 for governance domain coverage.

Purpose: These services complete the governance domain coverage. Proposal handles INTERN agent approvals, graduation validates maturity transitions, and context resolver provides agent ID resolution with fallbacks.

Output: Three new test files with 80%+ coverage for proposal, graduation governance logic, and context resolver services.

**IMPORTANT DISTINCTION:** This plan tests governance-specific graduation logic (maturity transitions, confidence scores, permission matrix). Plan 03 Task 5 tests episodic memory integration (episode counts, intervention rates, constitutional compliance). Each file focuses on different aspects of graduation_service.py with no duplication.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/05-coverage-quality-validation/05-RESEARCH.md

@backend/core/proposal_service.py
@backend/core/agent_graduation_service.py
@backend/core/agent_context_resolver.py
@backend/tests/property_tests/governance/test_governance_invariants.py
@backend/tests/factories/__init__.py

# Property tests from Phase 2 cover governance invariants
# This plan focuses on unit test coverage for individual service methods
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create unit tests for ProposalService</name>
  <files>backend/tests/unit/governance/test_proposal_service.py</files>
  <action>
Create comprehensive unit tests for ProposalService covering:

1. **Proposal generation**:
   - Test generating proposals for INTERN agents
   - Verify proposal includes: action, complexity, risk assessment, estimated impact
   - Test proposal format and required fields

2. **Approval workflow**:
   - Test proposal submission for human approval
   - Test approval acceptance (execute action)
   - Test proposal rejection (log and block)
   - Test proposal expiration

3. **Risk assessment**:
   - Test risk calculation based on action complexity and agent confidence
   - Verify risk levels (LOW, MEDIUM, HIGH, CRITICAL)
   - Test risk mitigation suggestions

4. **Audit trail**:
   - Verify all proposals logged to AgentProposal
   - Test proposal history retrieval
   - Verify approval/rejection tracking

5. **Performance**:
   - Verify proposal generation <500ms (per research)
   - Test with concurrent proposal requests

Use factories for AgentProposal model.
Mock approval storage (database or in-memory).

DO NOT test actual approval UI (that's frontend).
Focus on service-level proposal logic.
  </action>
  <verify>
pytest tests/unit/governance/test_proposal_service.py -v --cov=core/proposal_service --cov-report=term-missing
  </verify>
  <done>
Coverage for proposal_service.py >= 80%
All tests pass with pytest -v
  </done>
</task>

<task type="auto">
  <name>Task 2: Create unit tests for AgentGraduationService (governance logic)</name>
  <files>backend/tests/unit/governance/test_agent_graduation_governance.py</files>
  <action>
Create comprehensive unit tests for governance-specific graduation logic covering:

**SCOPE:** This test file focuses on governance logic (maturity level transitions, confidence scores, permission matrix validation).

1. **Maturity level transitions**:
   - Test STUDENT -> INTERN transition validation
   - Test INTERN -> SUPERVISED transition validation
   - Test SUPERVISED -> AUTONOMOUS transition validation
   - Test invalid transitions (rejection)

2. **Confidence score thresholds**:
   - Test minimum confidence for each maturity level
   - Test confidence score calculation from execution history
   - Test confidence score normalization

3. **Permission matrix validation**:
   - Test that permission matrix is updated on graduation
   - Test permission revocation on demotion
   - Test permission inheritance between maturity levels

4. **Graduation request processing**:
   - Test graduation request submission
   - Test graduation request validation
   - Test graduation request approval/rejection

5. **Graduation audit logging**:
   - Test graduation events logged to database
   - Test audit trail includes: old level, new level, reason, timestamp
   - Test audit history retrieval

**NOTE:** Episodic memory integration (episode counts, intervention rates, constitutional compliance) is tested in Plan 03 Task 5 (test_agent_graduation_service.py in episodes/ directory). This file (test_agent_graduation_governance.py) tests governance logic only.

Use pytest-mock for mocking dependencies.
Use factories for AgentRegistry model.

DO NOT duplicate episodic memory tests from Plan 03.
DO NOT test episode counting or intervention rate calculation here.
Focus on governance-specific logic only.
  </action>
  <verify>
pytest tests/unit/governance/test_agent_graduation_governance.py -v --cov=core/agent_graduation_service --cov-report=term-missing
  </verify>
  <done>
Coverage for governance logic in agent_graduation_service.py >= 80%
All tests pass with pytest -v
No overlap with Plan 03 episodic memory tests
  </done>
</task>

<task type="auto">
  <name>Task 3: Create unit tests for AgentContextResolver</name>
  <files>backend/tests/unit/governance/test_agent_context_resolver.py</files>
  <action>
Create comprehensive unit tests for AgentContextResolver covering:

1. **Fallback chain resolution**:
   - Test direct agent ID lookup
   - Test session-based resolution
   - Test workflow-based resolution
   - Test default/guest context

2. **Cache integration**:
   - Test GovernanceCache for context lookup
   - Verify cache hit/miss behavior
   - Test cache invalidation

3. **Error handling**:
   - Test missing agent ID (return default context)
   - Test database errors (graceful degradation)
   - Test malformed context data

4. **Performance**:
   - Verify resolution <50ms average (per PERFORMANCE_TARGETS)
   - Test batch resolution for multiple agents

5. **Context enrichment**:
   - Test context merging from multiple sources
   - Test metadata attachment (timestamp, source)
   - Test context validation

Mock GovernanceCache and database queries.
Use fixtures for test context data.

DO NOT test actual governance decisions (those are in governance service tests).
Focus on context resolution logic only.
  </action>
  <verify>
pytest tests/unit/governance/test_agent_context_resolver.py -v --cov=core/agent_context_resolver --cov-report=term-missing
  </verify>
  <done>
Coverage for agent_context_resolver.py >= 80%
All tests pass with pytest -v
  </done>
</task>

</tasks>

<verification>
After all tasks complete:

1. Run all governance unit tests:
   ```bash
   pytest tests/unit/governance/test_proposal_service.py tests/unit/governance/test_agent_graduation_governance.py tests/unit/governance/test_agent_context_resolver.py -v --cov=core/proposal_service --cov=core/agent_graduation_service --cov=core/agent_context_resolver --cov-report=term-missing
   ```

2. Verify each file achieves >= 80% coverage

3. Verify all tests pass in parallel:
   ```bash
   pytest tests/unit/governance/test_proposal_service.py tests/unit/governance/test_agent_graduation_governance.py tests/unit/governance/test_agent_context_resolver.py -n auto --dist loadscope
   ```

4. Verify no overlap with Plan 03 episodic memory tests:
   ```bash
   # Verify this file tests governance logic
   grep -l "maturity.*transition\|permission.*matrix" tests/unit/governance/test_agent_graduation_governance.py

   # Verify Plan 03 tests episodic memory
   grep -l "episode.*count\|intervention.*rate" tests/unit/episodes/test_agent_graduation_service.py
   ```
</verification>

<success_criteria>
1. All three governance service files have >= 80% code coverage
2. All tests pass with pytest -v
3. All tests pass in parallel with pytest-xdist
4. Zero test failures when run 10 times sequentially (no flaky tests)
5. No test overlap with Plan 03 episodic memory tests
6. Total governance domain coverage >= 80% (combined with Plan 01a)
</success_criteria>

<output>
After completion, create `.planning/phases/05-coverage-quality-validation/05-01b-SUMMARY.md` with:
- Coverage achieved for each file
- Total number of tests added
- Any discovered bugs or issues
- Confirmation of no overlap with Plan 03 tests
</output>
