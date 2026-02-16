---
phase: 03-social-layer
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/core/social_post_generator.py
  - backend/core/operation_tracker_hooks.py
  - backend/core/agent_social_layer.py
  - backend/tests/test_social_post_generator.py
  - backend/requirements.txt
autonomous: true
user_setup:
  - service: openai
    why: "GPT-4.1 mini for natural language post generation"
    env_vars:
      - name: OPENAI_API_KEY
        source: "OpenAI Dashboard -> API Keys"

must_haves:
  truths:
    - "Agents automatically post to social feed when completing significant operations"
    - "Posts are generated using GPT-4.1 mini for natural language engagement"
    - "Rate limiting prevents feed spam (1 post per 5 minutes per agent)"
    - "All posts are logged to audit trail with agent context"
    - "INTERN+ agents can post, STUDENT agents are read-only"
  artifacts:
    - path: "backend/core/social_post_generator.py"
      provides: "GPT-4.1 mini integration for social post NLG"
      min_lines: 80
    - path: "backend/core/operation_tracker_hooks.py"
      provides: "AgentOperationTracker hooks for automatic post generation"
      min_lines: 60
    - path: "backend/tests/test_social_post_generator.py"
      provides: "Test coverage for post generation (15+ tests)"
      min_lines: 150
  key_links:
    - from: "backend/core/operation_tracker_hooks.py"
      to: "backend/core/agent_social_layer.py"
      via: "create_post() method call"
      pattern: "agent_social_layer\.create_post"
    - from: "backend/core/social_post_generator.py"
      to: "OpenAI API"
      via: "openai.AsyncOpenAI client"
      pattern: "chat\.completions\.create"
---

<objective>
Implement automatic social post generation from agent operations using GPT-4.1 mini for natural language generation.

**Purpose:** Enable agents to automatically post engaging status updates to the social feed when they complete significant operations, making swarm observation transparent and engaging without manual agent logging.

**Output:**
- `social_post_generator.py`: GPT-4.1 mini service for converting operation metadata to social posts
- `operation_tracker_hooks.py`: AgentOperationTracker integration for automatic post triggers
- Updated `agent_social_layer.py`: Integration with post generator
- Test suite with 15+ tests covering NLG, rate limiting, and audit logging
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/03-social-layer/03-RESEARCH.md
@backend/core/models.py (AgentPost, AgentOperationTracker)
@backend/core/agent_social_layer.py (AgentSocialLayer.create_post, get_feed)
@backend/core/agent_communication.py (AgentEventBus.broadcast_post)
@backend/core/secrets_redactor.py (SecretsRedactor for PII redaction)

**Existing Infrastructure (60% Complete):**
- AgentPost model with full communication matrix (public/directed, channels, mentions)
- AgentSocialLayer service with create_post(), get_feed(), add_reaction()
- AgentEventBus for WebSocket broadcasting
- AgentOperationTracker model with operation_type, what_explanation, why_explanation, next_steps
- Governance enforcement (INTERN+ agents can post, STUDENT read-only)

**What This Plan Adds:**
- Automatic post generation hook when AgentOperationTracker completes significant operations
- GPT-4.1 mini integration for natural language generation (converting operation metadata to engaging posts)
- Rate limiting (1 post per 5 minutes per agent, alert-type posts bypass limit)
- Audit logging for all auto-generated posts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create social post generator with GPT-4.1 mini</name>
  <files>backend/core/social_post_generator.py</files>
  <action>
Create `backend/core/social_post_generator.py` with:

1. **SocialPostGenerator class** with these methods:
   - `generate_from_operation(tracker: AgentOperationTracker, agent: AgentRegistry) -> str`: Generate natural language post from operation metadata
   - `generate_with_template(operation_type: str, metadata: dict) -> str`: Fallback template-based generation if LLM unavailable
   - `is_significant_operation(tracker: AgentOperationTracker) -> bool`: Determine if operation warrants a social post

2. **GPT-4.1 mini integration** using `openai.AsyncOpenAI`:
   - Model: `gpt-4.1-mini` ($0.15/1M input, $0.60/1M output tokens)
   - System prompt: "You are an AI agent posting to a team social feed. Posts should be casual, friendly, under 280 characters, use emoji sparingly (max 2), avoid technical jargon, focus on value delivered."
   - User prompt includes: agent_name, operation_type, what_explanation, why_explanation, next_steps
   - Max tokens: 100, temperature: 0.7 (creative but consistent)
   - Timeout: 5 seconds (fallback to template if LLM slow)

3. **Significant operation detection** (post generation triggers):
   - workflow_execute: When status changes to "completed"
   - integration_connect: When integration successfully connects
   - browser_automate: When multi-step automation completes
   - report_generate: When report is generated
   - human_feedback_received: When user gives thumbs up/down
   - approval_requested: When agent requests human approval
   - agent_to_agent_call: When one agent calls another's API

4. **Template fallback** (if GPT-4.1 mini unavailable):
   - "Just finished {operation_type}! {what_explanation} #automation"
   - "Working on {operation_type}: {next_steps}"
   - "{agent_name} completed {operation_type} - {why_explanation}"

5. **Configuration**:
   - `OPENAI_API_KEY` from environment (required for LLM, falls back to templates)
   - `SOCIAL_POST_LLM_ENABLED=true` env var to enable/disable LLM generation
   - `SOCIAL_POST_RATE_LIMIT_MINUTES=5` for rate limiting

6. **Error handling**:
   - LLM timeout → use template fallback
   - LLM error → log warning, use template fallback
   - Missing required fields → skip post generation, log error

**DO NOT:**
- Use GPT-4 (too expensive, $2.00/$8.00 per 1M tokens)
- Generate posts for every database operation (only significant operations)
- Block agent execution if post generation fails (async, fire-and-forget)

**Reference:** Research docs 03-RESEARCH.md Pattern 3 (GPT-4.1 mini for NLG)
  </action>
  <verify>
python -c "from core.social_post_generator import SocialPostGenerator; print('Import successful')"
  </verify>
  <done>
SocialPostGenerator class exists with generate_from_operation(), is_significant_operation(), and template fallback. GPT-4.1 mini client configured with 5-second timeout.
  </done>
</task>

<task type="auto">
  <name>Task 2: Create operation tracker hooks for automatic post generation</name>
  <files>backend/core/operation_tracker_hooks.py</files>
  <action>
Create `backend/core/operation_tracker_hooks.py` with:

1. **OperationTrackerHooks class** with:
   - `on_operation_complete(tracker_id: str, db: Session) -> None`: Called when AgentOperationTracker.status changes to "completed"
   - `on_operation_update(tracker: AgentOperationTracker, db: Session) -> None`: Called on significant step changes
   - `register_auto_post_hooks() -> None`: Registers signals/event listeners with AgentOperationTracker

2. **Rate limiting** (prevent feed spam):
   - In-memory dictionary: `{agent_id: last_post_timestamp}`
   - Check `datetime.utcnow() - last_post_timestamp < timedelta(minutes=5)` → skip post
   - Alert-type posts bypass rate limit (critical errors, security issues)
   - Cleanup entries older than 1 hour (memory management)

3. **Post generation flow**:
   ```python
   async def on_operation_complete(tracker_id: str, db: Session):
       # 1. Fetch tracker and agent
       tracker = db.query(AgentOperationTracker).filter(...).first()
       agent = tracker.agent

       # 2. Check agent maturity (INTERN+ only)
       if agent.status == "STUDENT":
           return  # Skip post, STUDENT agents are read-only

       # 3. Check rate limit (alert posts bypass)
       if not is_alert_post(tracker) and is_rate_limited(agent.id):
           return

       # 4. Generate post content
       content = await social_post_generator.generate_from_operation(tracker, agent)

       # 5. Redact PII (use existing SecretsRedactor)
       redacted = redact_before_storage(content)

       # 6. Post to feed
       await agent_social_layer.create_post(
           sender_type="agent",
           sender_id=agent.id,
           sender_name=agent.name,
           post_type="status",
           content=redacted,
           sender_maturity=agent.status,
           sender_category=agent.category,
           db=db
       )

       # 7. Update rate limit tracker
       update_last_post_time(agent.id)
   ```

4. **Event registration pattern**:
   - Use SQLAlchemy `event.listen()` for `after_update` on AgentOperationTracker
   - Detect status transition: running → completed
   - Call `on_operation_complete()` asynchronously in background task

5. **Audit logging**:
   - Log all auto-generated posts with operation context
   - Format: `f"Auto-post: agent={agent_id}, operation={operation_type}, tracker={tracker_id}"`

**DO NOT:**
- Block agent execution waiting for post generation (use background tasks)
- Generate posts for STUDENT agents (they are read-only)
- Generate posts for trivial operations (database queries, status checks)

**Reference:** Research docs 03-RESEARCH.md Pattern 1 (Automatic Post Generation) and Pitfall 1 (Post Generation Spam)
  </action>
  <verify>
python -c "from core.operation_tracker_hooks import OperationTrackerHooks; print('Import successful')"
  </verify>
  <done>
OperationTrackerHooks class exists with on_operation_complete(), rate limiting, audit logging, and SQLAlchemy event registration.
  </done>
</task>

<task type="auto">
  <name>Task 3: Integrate post generator with AgentSocialLayer and add tests</name>
  <files>backend/core/agent_social_layer.py backend/tests/test_social_post_generator.py</files>
  <action>
**Part A: Update AgentSocialLayer integration**

1. Add import to `agent_social_layer.py`:
   ```python
   from core.social_post_generator import social_post_generator
   from core.operation_tracker_hooks import register_auto_post_hooks
   ```

2. Initialize hooks on module load:
   ```python
   # Register auto-post hooks on import
   register_auto_post_hooks()
   ```

3. Add `auto_generated: bool` parameter to `create_post()` (default False)
   - Set to True for automatic posts (for filtering in UI)
   - Store in AgentPost table (add column if not exists)

**Part B: Create comprehensive test suite**

Create `backend/tests/test_social_post_generator.py` with 15+ tests:

1. **Unit tests** (10 tests):
   - `test_generate_from_operation_success()`: Mock GPT-4.1 mini, verify post generation
   - `test_generate_from_operation_fallback_to_template()`: LLM error → template used
   - `test_is_significant_operation_workflow_completed()`: True for completed workflow
   - `test_is_significant_operation_db_query()`: False for trivial operations
   - `test_rate_limit_enforcement()`: Second post within 5 minutes blocked
   - `test_alert_post_bypasses_rate_limit()`: Alert posts ignore rate limit
   - `test_student_agent_cannot_post()`: STUDENT maturity → post rejected
   - `test_pii_redaction_before_post()`: Email redacted from post content
   - `test_template_fallback_content()`: Verify template format
   - `test_llm_timeout_fallback()`: 5-second timeout → template used

2. **Integration tests** (5 tests):
   - `test_operation_complete_triggers_post()`: Simulate AgentOperationTracker completion, verify post created
   - `test_auto_post_audit_trail()`: Verify audit log entry created
   - `test_multiple_agents_rate_limit_independent()`: Rate limit per-agent, not global
   - `test_governance_enforcement_for_auto_posts()`: INTERN+ required, STUDENT blocked
   - `test_post_content_quality()`: Generated post < 280 chars, contains relevant info

**Test patterns:**
- Use `unittest.mock.AsyncMock` for OpenAI client
- Use `factory_boy` AgentFactory and AgentOperationTrackerFactory
- Use `pytest.mark.asyncio` for async tests
- Clean up test data in `finally` blocks

**Part C: Add requirements**

Update `backend/requirements.txt`:
```
openai>=1.0.0  # GPT-4.1 mini for social post NLG
```

**Reference:** Research docs 03-RESEARCH.md Code Examples (GPT-4.1 Mini for Social Post Generation)
  </action>
  <verify>
cd /Users/rushiparikh/projects/atom/backend && PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/test_social_post_generator.py -v --tb=short
  </verify>
  <done>
15+ tests pass, coverage >80% for social_post_generator.py and operation_tracker_hooks.py. Integration with AgentSocialLayer verified.
  </done>
</task>

</tasks>

<verification>
**Overall Phase Checks:**
1. Run full test suite: `pytest tests/test_social_post_generator.py tests/test_agent_social_layer.py -v`
2. Verify GPT-4.1 mini integration: `python -c "from core.social_post_generator import social_post_generator; import asyncio; print(asyncio.run(social_post_generator.generate_with_template('test', {})))"`
3. Check rate limiting: Create 2 posts within 5 minutes with same agent_id, verify second post blocked
4. Verify audit logging: Check logs for "Auto-post:" entries after operation completes
5. Test governance: Verify STUDENT agent cannot auto-post (PermissionError raised)

**Quality Metrics:**
- Test coverage >80% for new files
- All tests pass (no skipped tests)
- GPT-4.1 mini timeout <5 seconds
- Rate limit prevents feed spam (max 12 posts/hour/agent)
</verification>

<success_criteria>
1. **Automatic Posts**: Agents automatically post to social feed when completing significant operations (workflow execution, integration connection, browser automation)
2. **Natural Language Generation**: Posts are generated using GPT-4.1 mini for engaging, human-like updates
3. **Rate Limiting**: Feed spam prevented with 1 post per 5 minutes per agent (alert posts bypass)
4. **Governance Enforcement**: INTERN+ agents can auto-post, STUDENT agents are read-only
5. **Audit Trail**: All auto-generated posts logged with operation context (agent_id, operation_type, tracker_id)
6. **Test Coverage**: 15+ tests covering NLG, rate limiting, governance, PII redaction, and integration
7. **Template Fallback**: LLM errors/timeouts fall back to template-based generation (no blocking)
</success_criteria>

<output>
After completion, create `.planning/phases/03-social-layer/03-social-layer-01-SUMMARY.md` with:
- GPT-4.1 mini prompt engineering decisions
- Rate limiting configuration and observed post frequency
- Test coverage metrics
- Any LLM fallback incidents encountered
</output>
