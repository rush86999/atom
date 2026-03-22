---
phase: 212-80pct-coverage-clean-slate
plan: WAVE3A
type: execute
wave: 3
depends_on: ["212-WAVE2A", "212-WAVE2B", "212-WAVE2C", "212-WAVE2D"]
files_modified:
  - backend/tests/test_episode_lifecycle_service.py
  - backend/tests/test_agent_world_model.py
  - backend/tests/test_policy_fact_extractor.py
  - backend/tests/test_atom_cli_skill_wrapper.py
  - backend/tests/test_models.py
autonomous: true

must_haves:
  truths:
    - "episode_lifecycle_service.py achieves 80%+ coverage"
    - "agent_world_model.py achieves 80%+ coverage"
    - "policy_fact_extractor.py achieves 80%+ coverage"
    - "atom_cli_skill_wrapper.py achieves 80%+ coverage"
    - "models.py achieves 60%+ coverage (focus on critical models)"
    - "Backend coverage increases from 45% to 65%+"
  artifacts:
    - path: "backend/tests/test_episode_lifecycle_service.py"
      provides: "Unit tests for EpisodeLifecycleService"
      min_lines: 350
      exports: ["TestEpisodeLifecycle", "TestEpisodeDecay"]
    - path: "backend/tests/test_agent_world_model.py"
      provides: "Unit tests for WorldModelService"
      min_lines: 400
      exports: ["TestWorldModelService", "TestBusinessFacts"]
    - path: "backend/tests/test_policy_fact_extractor.py"
      provides: "Unit tests for PolicyFactExtractor"
      min_lines: 300
      exports: ["TestPolicyFactExtractor", "TestPDFExtraction"]
    - path: "backend/tests/test_atom_cli_skill_wrapper.py"
      provides: "Unit tests for AtomCliSkillWrapper"
      min_lines: 300
      exports: ["TestCommandExecution", "TestCommandValidation"]
    - path: "backend/tests/test_models.py"
      provides: "Unit tests for database models"
      min_lines: 400
      exports: ["TestAgentRegistry", "TestEpisode", "TestBusinessFact"]
  key_links:
    - from: "backend/tests/test_episode_lifecycle_service.py"
      to: "backend/core/episode_lifecycle_service.py"
      via: "Direct imports and mock database"
    - from: "backend/tests/test_agent_world_model.py"
      to: "backend/core/agent_world_model.py"
      via: "Direct imports and mock LanceDB"
    - from: "backend/tests/test_models.py"
      to: "backend/core/models.py"
      via: "Direct imports and mock database sessions"
---

<objective>
Increase backend coverage from 45% to 65% by testing core services (lifecycle, world model, policy, CLI, models).

Purpose: These services handle episodic memory lifecycle, business facts/JIT verification, policy extraction, CLI execution, and core database models. They are foundational to agent intelligence and system reliability.

Output: 5 test files with 1,750+ total lines, achieving backend 65%+ coverage.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md
@backend/core/episode_lifecycle_service.py
@backend/core/agent_world_model.py
@backend/core/policy_fact_extractor.py
@backend/tools/atom_cli_skill_wrapper.py
@backend/core/models.py

# Test Pattern Reference
From Phase 216: Use AsyncMock for async methods, patch services at import location, mock database sessions with SessionLocal fixtures.

# Target Backend Files Analysis

## 1. episode_lifecycle_service.py (~300 lines)
Key methods:
- create_episode(): Create new episode
- decay_episode(): Decay old episodes
- consolidate_episode(): Merge related episodes
- archive_episode(): Archive to cold storage
- get_episode_stats(): Get episode statistics

## 2. agent_world_model.py (~500 lines)
Key methods:
- record_experience(): Record agent experience
- retrieve_experiences(): Retrieve relevant experiences
- create_business_fact(): Create business fact
- verify_citation(): Verify fact citation
- semantic_search(): Semantic fact search

## 3. policy_fact_extractor.py (~300 lines)
Key methods:
- extract_facts_from_document(): Extract facts from PDF
- parse_policy_document(): Parse policy structure
- detect_citations(): Detect citations in text
- validate_citation_format(): Validate citation format

## 4. atom_cli_skill_wrapper.py (~250 lines)
Key methods:
- execute_cli_command(): Execute CLI command
- parse_cli_output(): Parse command output
- handle_timeout(): Handle command timeout
- validate_command(): Validate command against whitelist

## 5. models.py (~4,200 lines)
Key models:
- AgentRegistry: Agent registration
- AgentExecution: Execution tracking
- Episode: Episode data
- EpisodeSegment: Segment data
- BusinessFact: Business facts
- 20+ other models (focus on critical 10)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create tests for episode_lifecycle_service</name>
  <files>backend/tests/test_episode_lifecycle_service.py</files>
  <action>
Create backend/tests/test_episode_lifecycle_service.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.episode_lifecycle_service import EpisodeLifecycleService

2. Fixtures:
   - mock_service(): Returns EpisodeLifecycleService
   - mock_episode(): Returns test Episode

3. Class TestEpisodeCreation:
   - test_create_episode(): Creates new episode
   - test_create_episode_with_segments(): Includes segments
   - test_create_episode_auto_title(): Auto-generates title
   - test_create_episode_links_to_agent(): Links to agent

4. Class TestEpisodeDecay:
   - test_decay_old_episode(): Decays episodes older than threshold
   - test_decay_preserves_recent(): Preserves recent episodes
   - test_decay_reduces_access_score(): Reduces access score
   - test_no_decay_below_threshold(): Stops at minimum score

5. Class TestEpisodeConsolidation:
   - test_consolidate_related_episodes(): Merges related episodes
   - test_consolidation_preserves_segments(): Preserves all segments
   - test_consolidation_updates_metadata(): Updates metadata
   - test_no_consolidation_unrelated(): Rejects unrelated episodes

6. Class TestEpisodeArchival:
   - test_archive_episode(): Archives to LanceDB
   - test_archive_batch(): Archives batch of episodes
   - test_archive_removes_from_hot(): Removes from PostgreSQL
   - test_archive_preserves_indexing(): Preserves search index

7. Class TestEpisodeStatistics:
   - test_get_episode_stats(): Returns episode statistics
   - test_stats_by_agent(): Groups by agent
   - test_stats_by_time_range(): Filters by time
   - test_stats_includes_feedback(): Includes feedback metrics

8. Mock database sessions, LanceDB client
  </action>
  <verify>
pytest backend/tests/test_episode_lifecycle_service.py -v
pytest backend/tests/test_episode_lifecycle_service.py --cov=core.episode_lifecycle_service --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All episode_lifecycle_service tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 2: Create tests for agent_world_model</name>
  <files>backend/tests/test_agent_world_model.py</files>
  <action>
Create backend/tests/test_agent_world_model.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.agent_world_model import WorldModelService, AgentExperience, BusinessFact

2. Fixtures:
   - mock_service(): Returns WorldModelService
   - mock_experience(): Returns test AgentExperience
   - mock_business_fact(): Returns test BusinessFact

3. Class TestExperienceRecording:
   - test_record_experience(): Records agent experience
   - test_record_experience_with_outcome(): Includes outcome
   - test_record_experience_with_learnings(): Includes learnings
   - test_experience_vector_embedding(): Creates vector embedding

4. Class TestExperienceRetrieval:
   - test_retrieve_by_agent(): Retrieves by agent_id
   - test_retrieve_by_task_type(): Filters by task type
   - test_retrieve_by_time_range(): Filters by time
   - test_retrieve_semantic(): Semantic similarity search
   - test_retrieve_top_k(): Returns top K results

5. Class TestBusinessFacts:
   - test_create_business_fact(): Creates business fact
   - test_fact_with_citation(): Includes citation
   - test_fact_verification(): Verifies citation
   - test_fact_semantic_search(): Semantic fact search
   - test_fact_by_id(): Retrieves by ID

6. Class TestCitationVerification:
   - test_verify_citation_valid(): Verifies valid citation
   - test_verify_citation_invalid(): Rejects invalid citation
   - test_verify_s3_citation(): Verifies S3 URI
   - test_verify_r2_citation(): Verifies R2 URI
   - test_verify_local_file(): Verifies local file

7. Mock LanceDB client, S3/R2 storage, PDF parser
  </action>
  <verify>
pytest backend/tests/test_agent_world_model.py -v
pytest backend/tests/test_agent_world_model.py --cov=core.agent_world_model --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All agent_world_model tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 3: Create tests for policy_fact_extractor</name>
  <files>backend/tests/test_policy_fact_extractor.py</files>
  <action>
Create backend/tests/test_policy_fact_extractor.py with comprehensive tests:

1. Imports: pytest, AsyncMock, from core.policy_fact_extractor import PolicyFactExtractor

2. Fixtures:
   - mock_extractor(): Returns PolicyFactExtractor
   - mock_pdf_content(): Returns test PDF bytes

3. Class TestPDFExtraction:
   - test_extract_from_pdf(): Extracts facts from PDF
   - test_extract_handles_encrypted_pdf(): Handles encrypted PDFs
   - test_extract_handles_corrupt_pdf(): Handles corrupt PDFs
   - test_extract_multi_page(): Handles multi-page PDFs

4. Class TestFactDetection:
   - test_detect_rules(): Detects rule statements
   - test_detect_policies(): Detects policy statements
   - test_detect_requirements(): Detects requirements
   - test_extract_confidence(): Extracts confidence score

5. Class TestCitationDetection:
   - test_detect_citations(): Detects in-text citations
   - test_parse_page_citation(): Parses "page:N" format
   - test_parse_section_citation(): Parses "section:N" format
   - test_validate_citation_format(): Validates format

6. Class TestFactStructuring:
   - test_structure_fact(): Structures fact with metadata
   - test_fact_with_source(): Includes source document
   - test_fact_with_context(): Includes surrounding context
   - test_fact_aggregation(): Aggregates related facts

7. Mock PyPDF2, pdfplumber, LLM extraction
  </action>
  <verify>
pytest backend/tests/test_policy_fact_extractor.py -v
pytest backend/tests/test_policy_fact_extractor.py --cov=core.policy_fact_extractor --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All policy_fact_extractor tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 4: Create tests for atom_cli_skill_wrapper</name>
  <files>backend/tests/test_atom_cli_skill_wrapper.py</files>
  <action>
Create backend/tests/test_atom_cli_skill_wrapper.py with comprehensive tests:

1. Imports: pytest, from tools.atom_cli_skill_wrapper import AtomCliSkillWrapper

2. Fixtures:
   - mock_wrapper(): Returns AtomCliSkillWrapper
   - mock_subprocess_result(): Returns subprocess result

3. Class TestCommandExecution:
   - test_execute_daemon_command(): Executes daemon command
   - test_execute_status_command(): Executes status command
   - test_execute_start_command(): Executes start command
   - test_execute_stop_command(): Executes stop command
   - test_execute_config_command(): Executes config command

4. Class TestCommandValidation:
   - test_validate_whitelisted_command(): Allows whitelisted
   - test_validate_blocked_command(): Blocks non-whitelisted
   - test_validate_maturity_check(): Checks maturity level
   - test_autonomous_only_commands(): AUTONOMOUS only for some commands

5. Class TestOutputParsing:
   - test_parse_json_output(): Parses JSON output
   - test_parse_text_output(): Parses text output
   - test_parse_error_output(): Parses error output
   - test_handle_malformed_output(): Handles malformed output

6. Class TestTimeoutHandling:
   - test_timeout_after_30_seconds(): Times out after 30s
   - test_timeout_custom_duration(): Uses custom timeout
   - test_timeout_kills_process(): Kills process on timeout
   - test_timeout_returns_error(): Returns error on timeout

7. Mock subprocess.run, subprocess.Popen
  </action>
  <verify>
pytest backend/tests/test_atom_cli_skill_wrapper.py -v
pytest backend/tests/test_atom_cli_skill_wrapper.py --cov=tools.atom_cli_skill_wrapper --cov-report=term-missing
# Coverage should be 80%+
  </verify>
  <done>
All atom_cli_skill_wrapper tests passing, 80%+ coverage achieved
  </done>
</task>

<task type="auto">
  <name>Task 5: Create tests for database models</name>
  <files>backend/tests/test_models.py</files>
  <action>
Create backend/tests/test_models.py with comprehensive model tests:

1. Imports: pytest, from core.models import [all models]

2. Class TestAgentRegistry:
   - test_create_agent(): Creates agent with defaults
   - test_agent_maturity_enum(): Validates maturity values
   - test_agent_confidence_range(): Validates 0-1 range
   - test_agent_relationships(): Tests relationships

3. Class TestAgentExecution:
   - test_create_execution(): Creates execution record
   - test_execution_status_enum(): Validates status values
   - test_execution_timestamps(): Validates timestamps
   - test_execution_feedback_link(): Links to feedback

4. Class TestEpisode:
   - test_create_episode(): Creates episode
   - test_episode_segments(): Has many segments
   - test_episode_feedback_links(): Links to feedback
   - test_episode_canvas_links(): Links to canvas

5. Class TestEpisodeSegment:
   - test_create_segment(): Creates segment
   - test_segment_belongs_to_episode(): Belongs to episode
   - test_segment_embedding(): Has vector embedding

6. Class TestBusinessFact:
   - test_create_fact(): Creates business fact
   - test_fact_citations(): Has many citations
   - test_fact_verified(): Has verified flag
   - test_fact_embedding(): Has vector embedding

7. Class TestCanvasAudit:
   - test_create_audit(): Creates audit record
   - test_audit_links_to_canvas(): Links to canvas
   - test_audit_links_to_agent(): Links to agent

8. Use pytest fixtures for database sessions, test models

Note: Focus on critical models (AgentRegistry, AgentExecution, Episode, EpisodeSegment, BusinessFact, CanvasAudit, AgentFeedback, SupervisionSession, TrainingSession, CommunitySkill). Target 60%+ coverage on models.py (4,200 lines is too large for 80% in one wave).
  </action>
  <verify>
pytest backend/tests/test_models.py -v
pytest backend/tests/test_models.py --cov=core.models --cov-report=term-missing
# Coverage should be 60%+
  </verify>
  <done>
All models tests passing, 60%+ coverage achieved
  </done>
</task>

</tasks>

<verification>
After completing all tasks:

1. Run all backend tests:
   pytest backend/tests/test_episode_lifecycle_service.py \
          backend/tests/test_agent_world_model.py \
          backend/tests/test_policy_fact_extractor.py \
          backend/tests/test_atom_cli_skill_wrapper.py \
          backend/tests/test_models.py -v

2. Verify backend coverage (target 65%+):
   pytest backend/tests/ --cov=core --cov=tools --cov-report=json
   # Backend should be 65%+

3. Verify no regression in existing tests:
   pytest backend/tests/ -v
</verification>

<success_criteria>
1. All 5 test files pass (100% pass rate)
2. Episode, world model, policy, CLI services achieve 80%+ coverage
3. Models achieve 60%+ coverage (critical models)
4. Backend overall coverage >= 65%
5. No regression in existing test coverage
</success_criteria>

<output>
After completion, create `.planning/phases/212-80pct-coverage-clean-slate/212-WAVE3A-SUMMARY.md`
</output>
