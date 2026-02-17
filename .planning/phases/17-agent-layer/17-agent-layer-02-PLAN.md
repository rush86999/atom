---
phase: 17-agent-layer
plan: 02
type: execute
wave: 2
depends_on: [01]
files_modified:
  - backend/tests/unit/episodes/test_agent_graduation_readiness.py
  - backend/tests/unit/episodes/test_graduation_exam_execution.py
  - backend/tests/unit/governance/test_trigger_interceptor_routing.py
autonomous: true

must_haves:
  truths:
    - "Graduation readiness score calculates correctly (40% episodes, 30% intervention, 30% constitutional)"
    - "STUDENT→INTERN requires 10 episodes, 50% intervention rate, 0.70 constitutional score"
    - "INTERN→SUPERVISED requires 25 episodes, 20% intervention rate, 0.85 constitutional score"
    - "SUPERVISED→AUTONOMOUS requires 50 episodes, 0% intervention rate, 0.95 constitutional score"
    - "Trigger interceptor routes STUDENT agents to training (blocks automated triggers)"
    - "Trigger interceptor routes INTERN agents to proposal (requires approval)"
    - "Trigger interceptor routes SUPERVISED agents to supervision (real-time monitoring)"
    - "Context resolver fallback chain: explicit agent_id → session agent → system default"
  artifacts:
    - path: "backend/tests/unit/episodes/test_agent_graduation_readiness.py"
      provides: "Graduation readiness scoring tests (calculate_readiness_score)"
      min_lines: 350
    - path: "backend/tests/unit/episodes/test_graduation_exam_execution.py"
      provides: "Graduation exam sandbox execution tests (execute_exam, validate_constitutional)"
      min_lines: 350
    - path: "backend/tests/unit/governance/test_trigger_interceptor_routing.py"
      provides: "Trigger interceptor maturity-based routing tests (4 routing paths)"
      min_lines: 400
  key_links:
    - from: "test_agent_graduation_readiness.py"
      to: "core/agent_graduation_service.py"
      via: "AgentGraduationService.calculate_readiness_score() method"
      pattern: "calculate_readiness_score"
    - from: "test_graduation_exam_execution.py"
      to: "core/agent_graduation_service.py"
      via: "SandboxExecutor.execute_exam() and validate_constitutional_compliance()"
      pattern: "execute_exam|validate_constitutional_compliance"
    - from: "test_trigger_interceptor_routing.py"
      to: "core/trigger_interceptor.py"
      via: "TriggerInterceptor.intercept_trigger() and routing methods"
      pattern: "intercept_trigger|_route_.*_agent"
---

<objective>
Test agent graduation readiness scoring and trigger interceptor maturity-based routing.

**Purpose:** Validate that agent promotion decisions are data-driven using episodic memory metrics (episode count, intervention rate, constitutional compliance) and that automated triggers are routed correctly based on agent maturity levels.

**Output:** Three comprehensive test files covering:
1. Graduation readiness score calculation for all 3 promotion thresholds
2. Graduation exam sandbox execution with edge case validation
3. Trigger interceptor routing for all 4 maturity levels with fallback chain

**Coverage Target:** 55%+ combined coverage on agent_graduation_service.py and trigger_interceptor.py
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md

# Graduation and routing services
@backend/core/agent_graduation_service.py
@backend/core/trigger_interceptor.py
@backend/core/agent_context_resolver.py

# Existing test patterns
@backend/tests/unit/episodes/test_agent_graduation_service.py
@backend/tests/unit/governance/test_agent_context_resolver.py
@backend/tests/conftest.py (db_session, maturity fixtures)
@backend/tests/factories/__init__.py (AgentFactory, EpisodeFactory)
</context>

<tasks>

<task type="auto">
  <name>Test graduation readiness score calculation</name>
  <files>backend/tests/unit/episodes/test_agent_graduation_readiness.py</files>
  <action>
    Create test_agent_graduation_readiness.py with graduation readiness calculation tests.

    Test classes:
    - TestReadinessScoreCalculation: 4 tests for score calculation (40% episodes, 30% intervention, 30% constitutional)
    - TestINTERNGraduationCriteria: 4 tests for STUDENT→INTERN requirements (10 episodes, 50% intervention, 0.70 constitutional)
    - TestSUPERVISEDGraduationCriteria: 4 tests for INTERN→SUPERVISED requirements (25 episodes, 20% intervention, 0.85 constitutional)
    - TestAUTONOMOUSGraduationCriteria: 4 tests for SUPERVISED→AUTONOMOUS requirements (50 episodes, 0% intervention, 0.95 constitutional)
    - TestReadinessGapIdentification: 4 tests for gap detection (missing episodes, high intervention, low constitutional)
    - TestRecommendationGeneration: 4 tests for human-readable recommendations based on score
    - TestEdgeCases: 4 tests for boundary conditions (zero episodes, perfect agent, overflow scores)

    Use EpisodeFactory to create test episodes with various maturity_at_time values:
    ```python
    def test_intern_graduation_with_sufficient_episodes(self, db_session):
        agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        # Create 10 completed episodes at STUDENT maturity
        for i in range(10):
            episode = EpisodeFactory(
                agent_id=agent.id,
                maturity_at_time="student",
                status="completed",
                human_intervention_count=3,  # 30% rate
                constitutional_score=0.75
            )
            db_session.add(episode)
        db_session.commit()

        service = AgentGraduationService(db_session)
        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["ready"] is True
        assert result["score"] >= 70.0
        assert len(result["gaps"]) == 0
    ```

    Test score calculation formula:
    - Episode score (40%): min(episode_count / min_episodes, 1.0) * 40
    - Intervention score (30%): (1 - min(intervention_rate / max_intervention, 1.0)) * 30
    - Constitutional score (30%): min(constitutional_score / min_constitutional, 1.0) * 30

    Test gap identification:
    ```python
    def test_gap_identification_insufficient_episodes(self, db_session):
        agent = StudentAgentFactory(_session=db_session)

        # Only 5 episodes (need 10 for INTERN)
        for i in range(5):
            episode = EpisodeFactory(agent_id=agent.id, status="completed")
            db_session.add(episode)
        db_session.commit()

        service = AgentGraduationService(db_session)
        result = await service.calculate_readiness_score(
            agent_id=agent.id,
            target_maturity="INTERN"
        )

        assert result["ready"] is False
        assert any("5 more episodes" in gap for gap in result["gaps"])
    ```

    Test recommendation generation:
    ```python
    def test_recommendation_not_ready(self):
        service = AgentGraduationService(mock_db)
        recommendation = service._generate_recommendation(
            ready=False, score=40, target="INTERN"
        )

        assert "not ready" in recommendation.lower()
        assert "intern" in recommendation.lower()
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/episodes/test_agent_graduation_readiness.py -v

    Expected: 28 tests passing, readiness score calculation validated for all thresholds
  </verify>
  <done>
    - Readiness score formula validated (40/30/30 weighting)
    - All 3 graduation thresholds tested (INTERN, SUPERVISED, AUTONOMOUS)
    - Gap detection correctly identifies missing episodes, high intervention, low constitutional
    - Recommendations generated based on score ranges
    - Edge cases handled (zero episodes, overflow, perfect agent)
  </done>
</task>

<task type="auto">
  <name>Test graduation exam execution with sandbox validation</name>
  <files>backend/tests/unit/episodes/test_graduation_exam_execution.py</files>
  <action>
    Create test_graduation_exam_execution.py with sandbox exam execution tests.

    Test classes:
    - TestSandboxExecutorExecution: 4 tests for execute_exam() method (score calculation, violations, passing thresholds)
    - TestConstitutionalComplianceValidation: 4 tests for validate_constitutional_compliance() (compliant, violations, score)
    - TestGraduationExamIntegration: 4 tests for run_graduation_exam() (edge case scenarios, score aggregation)
    - TestPromotionWorkflow: 4 tests for promote_agent() (status update, metadata, audit trail)
    - TestSupervisionMetrics: 4 tests for calculate_supervision_metrics() (hours, intervention rate, ratings)
    - TestPerformanceTrends: 4 tests for _calculate_performance_trend() (improving, stable, declining)
    - TestSkillUsageMetrics: 4 tests for calculate_skill_usage_metrics() (executions, success rate, diversity)
    - TestEdgeCases: 4 tests (nonexistent agent, no episodes, malformed data)

    Mock SandboxExecutor for isolated testing:
    ```python
    @patch('core.agent_graduation_service.SandboxExecutor')
    def test_exam_passing_with_high_performance(self, mock_executor_class, db_session):
        agent = StudentAgentFactory(_session=db_session)

        # Mock successful exam with high scores
        mock_executor = MagicMock()
        mock_executor.execute_exam.return_value = {
            "success": True,
            "score": 0.85,
            "constitutional_compliance": 0.90,
            "passed": True,
            "constitutional_violations": [],
            "attempt": 1
        }
        mock_executor_class.return_value = mock_executor

        service = AgentGraduationService(db_session)
        result = await service.execute_graduation_exam(
            agent_id=agent.id,
            workspace_id="default",
            target_maturity="INTERN"
        )

        assert result["exam_completed"] is True
        assert result["passed"] is True
        assert result["score"] >= 0.70
    ```

    Test constitutional compliance validation:
    ```python
    async def test_constitutional_compliance_with_violations(self, db_session):
        service = AgentGraduationService(db_session)

        # Create episode with segments
        episode = EpisodeFactory()
        db_session.add(episode)

        # Create segments with violations
        for i in range(3):
            segment = EpisodeSegmentFactory(
                episode_id=episode.id,
                action_type="delete",
                segment_type="action",
                metadata={"constitutional_violation": True}
            )
            db_session.add(segment)
        db_session.commit()

        with patch('core.agent_graduation_service.ConstitutionalValidator') as mock_validator:
            mock_validator.return_value.validate_actions.return_value = {
                "compliant": False,
                "score": 0.60,
                "violations": ["unauthorized_deletion", "missing_approval"],
                "total_actions": 3,
                "checked_actions": 3
            }

            result = await service.validate_constitutional_compliance(episode.id)

            assert result["compliant"] is False
            assert result["score"] == 0.60
            assert len(result["violations"]) > 0
    ```

    Test performance trend calculation:
    ```python
    def test_performance_trend_improving(self):
        service = AgentGraduationService(mock_db)

        # Create supervision sessions with improving ratings
        sessions = []
        for i in range(10):
            session = MagicMock(spec=SupervisionSession)
            session.supervisor_rating = 3.0 + (i * 0.2)  # 3.0 to 4.8
            session.intervention_count = max(5 - i, 0)  # Decreasing interventions
            session.started_at = datetime.now()
            sessions.append(session)

        # Sort in descending order (most recent first)
        sessions.sort(key=lambda s: s.started_at, reverse=True)

        trend = service._calculate_performance_trend(sessions)
        assert trend == "improving"
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/episodes/test_graduation_exam_execution.py -v

    Expected: 32 tests passing, exam execution and constitutional compliance validated
  </verify>
  <done>
    - Sandbox executor correctly calculates scores (40/30/30 weighting)
    - Constitutional compliance validation detects violations and assigns scores
    - Graduation exam integrates edge case scenarios
    - Promotion workflow updates agent status and metadata
    - Supervision metrics calculated correctly (hours, intervention rate, ratings)
    - Performance trends detected (improving, stable, declining)
    - Skill usage metrics tracked (executions, success rate, diversity)
  </done>
</task>

<task type="auto">
  <name>Test trigger interceptor routing with fallback chain</name>
  <files>backend/tests/unit/governance/test_trigger_interceptor_routing.py</files>
  <action>
    Create test_trigger_interceptor_routing.py with maturity-based routing tests.

    Test classes:
    - TestManualTriggerRouting: 4 tests for MANUAL trigger source (always allowed with warnings)
    - TestStudentAgentRouting: 4 tests for STUDENT routing to training (blocks automated triggers)
    - TestInternAgentRouting: 4 tests for INTERN routing to proposal (requires approval)
    - TestSupervisedAgentRouting: 4 tests for SUPERVISED routing to supervision (real-time monitoring)
    - TestAutonomousAgentRouting: 4 tests for AUTONOMOUS routing to execution (full approval)
    - TestRoutingDecisionStructure: 4 tests for TriggerDecision response structure
    - TestBlockedTriggerCreation: 4 tests for BlockedTriggerContext audit records
    - TestAgentProposalCreation: 4 tests for AgentProposal generation (INTERN agents)
    - TestSupervisionSessionCreation: 4 tests for SupervisionSession creation (SUPERVISED agents)
    - TestMaturityCaching: 4 tests for _get_agent_maturity_cached() cache behavior

    Mock the governance cache for performance:
    ```python
    @patch('core.trigger_interceptor.get_async_governance_cache')
    async def test_student_agent_blocked_from_automated_trigger(self, mock_cache):
        # Mock cache to return STUDENT maturity
        cache_inst = AsyncMock()
        cache_inst.get.return_value = {
            "status": "student",
            "confidence": 0.4
        }
        mock_cache.return_value = cache_inst

        db = MagicMock()
        interceptor = TriggerInterceptor(db, workspace_id="test")

        decision = await interceptor.intercept_trigger(
            agent_id="student_agent",
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            trigger_context={"action_type": "create"},
            user_id=None
        )

        assert decision.routing_decision == RoutingDecision.TRAINING
        assert decision.execute is False
        assert "training proposal" in decision.reason.lower()
    ```

    Test proposal creation for INTERN agents:
    ```python
    @patch('core.trigger_interceptor.get_async_governance_cache')
    async def test_intern_agent_creates_proposal(self, mock_cache, db_session):
        cache_inst = AsyncMock()
        cache_inst.get.return_value = {"status": "intern", "confidence": 0.6}
        cache_inst.set = AsyncMock()
        mock_cache.return_value = cache_inst

        agent = InternAgentFactory(_session=db_session)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test")

        decision = await interceptor.intercept_trigger(
            agent_id=agent.id,
            trigger_source=TriggerSource.DATA_SYNC,
            trigger_context={"action_type": "update"},
            user_id=None
        )

        assert decision.routing_decision == RoutingDecision.PROPOSAL
        assert decision.execute is False
        assert decision.blocked_context is not None
    ```

    Test supervision for SUPERVISED agents:
    ```python
    @patch('core.trigger_interceptor.get_async_governance_cache')
    @patch('core.trigger_interceptor.UserActivityService')
    @patch('core.trigger_interceptor.SupervisedQueueService')
    async def test_supervised_agent_executes_with_monitoring(
        self, mock_queue, mock_activity, mock_cache, db_session
    ):
        cache_inst = AsyncMock()
        cache_inst.get.return_value = {"status": "supervised", "confidence": 0.8}
        mock_cache.return_value = cache_inst

        # Mock user available for supervision
        mock_activity.return_value.should_supervise.return_value = True

        agent = SupervisedAgentFactory(_session=db_session)
        db_session.commit()

        interceptor = TriggerInterceptor(db_session, workspace_id="test")

        decision = await interceptor.intercept_trigger(
            agent_id=agent.id,
            trigger_source=TriggerSource.AI_COORDINATOR,
            trigger_context={"action_type": "create"},
            user_id="test_user"
        )

        assert decision.routing_decision == RoutingDecision.SUPERVISION
        assert decision.execute is True
        assert "real-time monitoring" in decision.reason.lower()
    ```

    Test context resolver integration:
    ```python
    @patch('core.trigger_interceptor.AgentContextResolver')
    async def test_context_resolver_fallback_chain(self, mock_resolver_class, db_session):
        # Test fallback chain: explicit → session → system default
        agent = AgentFactory(_session=db_session)
        db_session.commit()

        mock_resolver = MagicMock()
        mock_resolver.resolve_agent_for_request = AsyncMock()
        mock_resolver.resolve_agent_for_request.return_value = (agent, {
            "resolution_path": ["explicit_agent_id"]
        })
        mock_resolver_class.return_value = mock_resolver

        # Create resolver instance to test fallback
        resolver = AgentContextResolver(db_session)

        # Test explicit agent ID (Level 1)
        resolved, context = await resolver.resolve_agent_for_request(
            user_id="test_user",
            requested_agent_id=agent.id
        )

        assert resolved.id == agent.id
        assert "explicit_agent_id" in context["resolution_path"]
    ```
  </action>
  <verify>
    Run: pytest backend/tests/unit/governance/test_trigger_interceptor_routing.py -v

    Expected: 40+ tests passing, all routing paths validated
  </verify>
  <done>
    - All 4 maturity levels route correctly (STUDENT→training, INTERN→proposal, SUPERVISED→supervision, AUTONOMOUS→execution)
    - Manual triggers always allowed regardless of maturity
    - BlockedTriggerContext audit records created for blocked triggers
    - AgentProposal generated for INTERN agents
    - SupervisionSession created for SUPERVISED agents
    - Context resolver fallback chain works (explicit → session → system default)
    - Cache integration provides <5ms routing decisions
  </done>
</task>

</tasks>

<verification>
After completing all tasks, run full test suite for graduation and routing:

```bash
pytest backend/tests/unit/episodes/test_agent_graduation_readiness.py -v --cov=backend/core/agent_graduation_service --cov-report=term-missing
pytest backend/tests/unit/episodes/test_graduation_exam_execution.py -v --cov=backend/core/agent_graduation_service --cov-report=term-missing
pytest backend/tests/unit/governance/test_trigger_interceptor_routing.py -v --cov=backend/core/trigger_interceptor --cov-report=term-missing
```

Success criteria:
- All 100+ tests passing (28+32+40)
- Coverage on agent_graduation_service.py >55%
- Coverage on trigger_interceptor.py >55%
- All graduation thresholds validated (INTERN, SUPERVISED, AUTONOMOUS)
- All routing paths tested (training, proposal, supervision, execution)
- Context resolver fallback chain working correctly
</verification>

<success_criteria>
1. Graduation readiness scores calculated correctly with 40/30/30 weighting
2. All 3 promotion thresholds enforced (episode count, intervention rate, constitutional)
3. Trigger interceptor routes all 4 maturity levels correctly
4. Audit records created for blocked triggers (BlockedTriggerContext)
5. AgentProposal and SupervisionSession created for INTERN/SUPERVISED agents
6. Context resolver fallback chain works (explicit → session → system default)
7. Cache integration provides <5ms routing decisions
</success_criteria>

<output>
After completion, create `.planning/phases/05-agent-layer/05-agent-layer-02-SUMMARY.md`
</output>
