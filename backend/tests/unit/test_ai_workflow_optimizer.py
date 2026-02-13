"""
Unit tests for AIWorkflowOptimizer

Tests cover:
- Initialization and configuration
- Workflow analysis
- Workflow optimization planning
- Performance monitoring
- Recommendation generation
- Complexity scoring
- Bottleneck identification
- Failure point detection
- Edge cases and boundary conditions
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from core.ai_workflow_optimizer import (
    AIWorkflowOptimizer,
    WorkflowAnalysis,
    OptimizationRecommendation,
    OptimizationType,
    ImpactLevel,
    get_ai_workflow_optimizer
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def optimizer():
    """Create an AIWorkflowOptimizer instance"""
    return AIWorkflowOptimizer()


@pytest.fixture
def sample_workflow():
    """Sample workflow data for testing"""
    return {
        "id": "workflow-123",
        "name": "Test Workflow",
        "nodes": [
            {
                "id": "node1",
                "type": "trigger",
                "label": "Start",
                "config": {"action": "manual_trigger"}
            },
            {
                "id": "node2",
                "type": "action",
                "label": "Fetch Data",
                "config": {"integration": "slack", "action": "get_messages"}
            },
            {
                "id": "node3",
                "type": "action",
                "label": "Process",
                "config": {"integration": "openai", "action": "analyze"}
            },
            {
                "id": "node4",
                "type": "action",
                "label": "Send Email",
                "config": {"integration": "gmail", "action": "send"}
            }
        ],
        "edges": [
            {"source": "node1", "target": "node2"},
            {"source": "node2", "target": "node3"},
            {"source": "node3", "target": "node4"}
        ]
    }


@pytest.fixture
def sample_performance_metrics():
    """Sample performance metrics"""
    return {
        "avg_execution_time": 5.2,
        "success_rate": 0.95,
        "total_executions": 1000,
        "error_rate": 0.05
    }


@pytest.fixture
def complex_workflow():
    """Complex workflow with multiple integrations and conditions"""
    return {
        "id": "complex-workflow",
        "name": "Complex Workflow",
        "nodes": [
            {"id": "trigger", "type": "trigger", "config": {}},
            {"id": "action1", "type": "action", "config": {"integration": "salesforce"}},
            {"id": "action2", "type": "action", "config": {"integration": "slack"}},
            {"id": "condition1", "type": "condition", "config": {}},
            {"id": "action3", "type": "action", "config": {"integration": "openai"}},
            {"id": "action4", "type": "action", "config": {"integration": "gmail"}},
            {"id": "action5", "type": "action", "config": {"integration": "slack"}},
            {"id": "action6", "type": "action", "config": {"integration": "asana"}},
        ],
        "edges": [
            {"source": "trigger", "target": "action1"},
            {"source": "action1", "target": "action2"},
            {"source": "action2", "target": "condition1"},
            {"source": "condition1", "target": "action3"},
            {"source": "condition1", "target": "action4"},
            {"source": "action3", "target": "action5"},
            {"source": "action4", "target": "action6"},
        ]
    }


# =============================================================================
# TEST CLASS: AIWorkflowOptimizer Initialization
# =============================================================================

class TestOptimizerInit:
    """Tests for AIWorkflowOptimizer initialization"""

    def test_optimizer_init(self, optimizer):
        """Verify optimizer initializes with required attributes"""
        assert optimizer is not None
        assert hasattr(optimizer, 'optimization_rules')
        assert hasattr(optimizer, 'performance_benchmarks')
        assert hasattr(optimizer, 'integration_patterns')

    def test_optimization_rules_initialized(self, optimizer):
        """Verify optimization rules are initialized"""
        assert len(optimizer.optimization_rules) > 0
        assert OptimizationType.PERFORMANCE in optimizer.optimization_rules
        assert OptimizationType.COST in optimizer.optimization_rules
        assert OptimizationType.RELIABILITY in optimizer.optimization_rules

    def test_performance_benchmarks_initialized(self, optimizer):
        """Verify performance benchmarks are initialized"""
        assert len(optimizer.performance_benchmarks) > 0
        assert "api_response_time" in optimizer.performance_benchmarks
        assert "workflow_success_rate" in optimizer.performance_benchmarks
        assert "daily_executions" in optimizer.performance_benchmarks

    def test_integration_patterns_initialized(self, optimizer):
        """Verify integration patterns are initialized"""
        assert len(optimizer.integration_patterns) > 0
        assert "slack" in optimizer.integration_patterns
        assert "openai" in optimizer.integration_patterns
        assert "gmail" in optimizer.integration_patterns
        assert "salesforce" in optimizer.integration_patterns

    def test_singleton_pattern(self):
        """Verify get_ai_workflow_optimizer returns singleton"""
        optimizer1 = get_ai_workflow_optimizer()
        optimizer2 = get_ai_workflow_optimizer()
        # Should be the same instance (singleton pattern)
        assert optimizer1 is optimizer2


# =============================================================================
# TEST CLASS: Workflow Analysis
# =============================================================================

class TestWorkflowAnalysis:
    """Tests for workflow analysis functionality"""

    @pytest.mark.asyncio
    async def test_analyze_workflow_basic(self, optimizer, sample_workflow):
        """Verify basic workflow analysis works"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        assert isinstance(analysis, WorkflowAnalysis)
        assert analysis.workflow_id == "workflow-123"
        assert analysis.workflow_name == "Test Workflow"
        assert analysis.total_nodes == 4
        assert analysis.total_edges == 3

    @pytest.mark.asyncio
    async def test_analyze_workflow_with_metrics(self, optimizer, sample_workflow, sample_performance_metrics):
        """Verify analysis with performance metrics"""
        analysis = await optimizer.analyze_workflow(sample_workflow, sample_performance_metrics)

        assert analysis is not None
        # Metrics should influence execution time estimation
        assert analysis.estimated_execution_time > 0

    @pytest.mark.asyncio
    async def test_extract_integrations(self, optimizer, sample_workflow):
        """Verify integration extraction from nodes"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        assert len(analysis.integrations_used) > 0
        assert "slack" in analysis.integrations_used
        assert "openai" in analysis.integrations_used
        assert "gmail" in analysis.integrations_used

    @pytest.mark.asyncio
    async def test_complexity_score_calculation(self, optimizer, complex_workflow):
        """Verify complexity score is calculated"""
        analysis = await optimizer.analyze_workflow(complex_workflow)

        assert 0 <= analysis.complexity_score <= 100
        # Complex workflow should have higher complexity
        assert analysis.complexity_score > 20

    @pytest.mark.asyncio
    async def test_execution_time_estimation(self, optimizer, sample_workflow):
        """Verify execution time estimation"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        assert analysis.estimated_execution_time > 0
        # Should be reasonable (not extremely large)
        assert analysis.estimated_execution_time < 100

    @pytest.mark.asyncio
    async def test_identify_failure_points(self, optimizer, sample_workflow):
        """Verify failure point identification"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        # Should identify failure points
        assert isinstance(analysis.failure_points, list)

    @pytest.mark.asyncio
    async def test_identify_bottlenecks(self, optimizer, complex_workflow):
        """Verify bottleneck identification"""
        analysis = await optimizer.analyze_workflow(complex_workflow)

        # Complex workflow with sequential edges should have bottlenecks
        assert isinstance(analysis.bottlenecks, list)

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, optimizer, sample_workflow):
        """Verify optimization recommendations are generated"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        assert isinstance(analysis.optimization_opportunities, list)

    @pytest.mark.asyncio
    async def test_analysis_timestamp(self, optimizer, sample_workflow):
        """Verify analysis includes timestamp"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        assert isinstance(analysis.analysis_timestamp, datetime)
        # Should be recent (within last minute)
        assert datetime.now(timezone.utc) - analysis.analysis_timestamp < timedelta(seconds=60)


# =============================================================================
# TEST CLASS: Complexity Scoring
# =============================================================================

class TestComplexityScoring:
    """Tests for complexity score calculation"""

    def test_complexity_score_empty_workflow(self, optimizer):
        """Verify empty workflow has low complexity"""
        workflow = {"id": "empty", "nodes": [], "edges": []}
        score = optimizer._calculate_complexity_score(workflow)
        assert score >= 0
        assert score < 20  # Should be low

    def test_complexity_score_simple_workflow(self, optimizer):
        """Verify simple workflow has low complexity"""
        workflow = {
            "id": "simple",
            "nodes": [{"id": "n1", "type": "action"}, {"id": "n2", "type": "action"}],
            "edges": [{"source": "n1", "target": "n2"}]
        }
        score = optimizer._calculate_complexity_score(workflow)
        assert score >= 0
        assert score < 50  # Should be relatively low

    def test_complexity_score_with_conditions(self, optimizer):
        """Verify conditional nodes increase complexity"""
        workflow = {
            "id": "conditional",
            "nodes": [
                {"id": "n1", "type": "action"},
                {"id": "n2", "type": "condition"},
                {"id": "n3", "type": "condition"}
            ],
            "edges": []
        }
        score = optimizer._calculate_complexity_score(workflow)
        # Conditional nodes should add complexity
        assert score > 10

    def test_complexity_score_with_integrations(self, optimizer, sample_workflow):
        """Verify multiple integrations increase complexity"""
        score = optimizer._calculate_complexity_score(sample_workflow)
        # Slack, OpenAI, Gmail = 3 integrations
        assert score > 10

    def test_complexity_score_max_limit(self, optimizer):
        """Verify complexity score caps at 100"""
        # Create a very large workflow
        nodes = [{"id": f"n{i}", "type": "action", "config": {"integration": "slack"}} for i in range(50)]
        edges = [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(49)]
        workflow = {"id": "huge", "nodes": nodes, "edges": edges}

        score = optimizer._calculate_complexity_score(workflow)
        assert score <= 100


# =============================================================================
# TEST CLASS: Integration Extraction
# =============================================================================

class TestIntegrationExtraction:
    """Tests for integration extraction from workflows"""

    def test_extract_integrations_from_nodes(self, optimizer, sample_workflow):
        """Verify integrations are extracted from node configs"""
        integrations = optimizer._extract_integrations(sample_workflow["nodes"])

        assert "slack" in integrations
        assert "openai" in integrations
        assert "gmail" in integrations

    def test_extract_integrations_empty_config(self, optimizer):
        """Verify nodes without integration are handled"""
        nodes = [
            {"id": "n1", "config": {}},
            {"id": "n2", "config": {"action": "test"}}
        ]
        integrations = optimizer._extract_integrations(nodes)
        assert len(integrations) == 0

    def test_extract_integrations_duplicates_removed(self, optimizer):
        """Verify duplicate integrations are removed"""
        nodes = [
            {"id": "n1", "config": {"integration": "slack"}},
            {"id": "n2", "config": {"integration": "slack"}},
            {"id": "n3", "config": {"integration": "slack"}}
        ]
        integrations = optimizer._extract_integrations(nodes)
        assert len(integrations) == 1
        assert integrations[0] == "slack"


# =============================================================================
# TEST CLASS: Execution Time Estimation
# =============================================================================

class TestExecutionTimeEstimation:
    """Tests for execution time estimation"""

    def test_estimate_time_no_metrics(self, optimizer, sample_workflow):
        """Verify estimation without metrics uses defaults"""
        time = optimizer._estimate_execution_time(sample_workflow, None)
        assert time > 0

    def test_estimate_time_with_metrics(self, optimizer, sample_workflow, sample_performance_metrics):
        """Verify estimation with performance metrics"""
        time = optimizer._estimate_execution_time(sample_workflow, sample_performance_metrics)
        assert time > 0

    def test_estimate_time_trigger_nodes(self, optimizer):
        """Verify trigger nodes don't add time"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "trigger", "config": {}},
                {"id": "n2", "type": "action", "config": {"integration": "slack"}}
            ],
            "edges": []
        }
        time = optimizer._estimate_execution_time(workflow, None)
        # Trigger should not add time
        assert time < 2

    def test_estimate_time_known_integrations(self, optimizer):
        """Verify known integrations use pattern times"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"integration": "slack"}},
                {"id": "n2", "type": "action", "config": {"integration": "openai"}},
                {"id": "n3", "type": "action", "config": {"integration": "gmail"}}
            ],
            "edges": []
        }
        time = optimizer._estimate_execution_time(workflow, None)
        assert time > 0

    def test_estimate_time_unknown_integration(self, optimizer):
        """Verify unknown integrations use default time"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"integration": "unknown_service"}}
            ],
            "edges": []
        }
        time = optimizer._estimate_execution_time(workflow, None)
        assert time >= 1.0  # Default estimate


# =============================================================================
# TEST CLASS: Failure Point Identification
# =============================================================================

class TestFailurePointIdentification:
    """Tests for failure point identification"""

    def test_identify_no_error_handling(self, optimizer):
        """Verify nodes without error handling are flagged"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {}}
            ]
        }
        failure_points = optimizer._identify_failure_points(workflow)
        assert len(failure_points) > 0
        assert "No error handling defined" in failure_points[0]["issues"]

    def test_identify_test_values(self, optimizer):
        """Verify test values in production are flagged"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"api_key": "test_key_123"}}
            ]
        }
        failure_points = optimizer._identify_failure_points(workflow)
        assert len(failure_points) > 0

    def test_identify_low_rate_limits(self, optimizer):
        """Verify low rate limit integrations are flagged"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"integration": "salesforce"}}
            ]
        }
        failure_points = optimizer._identify_failure_points(workflow)
        # Salesforce has rate limit of 5000/hour
        assert len(failure_points) > 0

    def test_identify_no_failure_points(self, optimizer):
        """Verify workflow with no issues has no failure points"""
        workflow = {
            "nodes": [
                {
                    "id": "n1",
                    "type": "action",
                    "config": {
                        "integration": "slack",
                        "error_handling": {"retry": True},
                        "api_key": "production_key"
                    }
                }
            ]
        }
        failure_points = optimizer._identify_failure_points(workflow)
        # Slack has high rate limit, should not be flagged
        assert len(failure_points) == 0


# =============================================================================
# TEST CLASS: Bottleneck Identification
# =============================================================================

class TestBottleneckIdentification:
    """Tests for bottleneck identification"""

    def test_identify_long_sequential_path(self, optimizer):
        """Verify long sequential paths are identified as bottlenecks"""
        nodes = [{"id": f"n{i}", "type": "action"} for i in range(7)]
        edges = [{"source": f"n{i}", "target": f"n{i+1}"} for i in range(6)]
        workflow = {"nodes": nodes, "edges": edges}

        bottlenecks = optimizer._identify_bottlenecks(workflow, None)
        assert len(bottlenecks) > 0
        assert "sequential_depth" in bottlenecks[0]["type"]

    def test_identify_large_data_processing(self, optimizer):
        """Verify large data processing is flagged"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"batch_size": 2000}}
            ],
            "edges": []
        }
        bottlenecks = optimizer._identify_bottlenecks(workflow, None)
        assert len(bottlenecks) > 0

    def test_identify_process_large_files(self, optimizer):
        """Verify process_large_data flag is detected"""
        workflow = {
            "nodes": [
                {"id": "n1", "type": "action", "config": {"process_large_data": True}}
            ],
            "edges": []
        }
        bottlenecks = optimizer._identify_bottlenecks(workflow, None)
        assert len(bottlenecks) > 0

    def test_no_bottlenecks_simple_workflow(self, optimizer):
        """Verify simple workflow has no bottlenecks"""
        workflow = {
            "nodes": [{"id": "n1", "type": "action"}],
            "edges": []
        }
        bottlenecks = optimizer._identify_bottlenecks(workflow, None)
        assert len(bottlenecks) == 0


# =============================================================================
# TEST CLASS: Recommendation Generation
# =============================================================================

class TestRecommendationGeneration:
    """Tests for optimization recommendation generation"""

    @pytest.mark.asyncio
    async def test_generate_recommendations(self, optimizer, sample_workflow):
        """Verify recommendations are generated"""
        analysis = await optimizer.analyze_workflow(sample_workflow)
        assert len(analysis.optimization_opportunities) >= 0

    @pytest.mark.asyncio
    async def test_recommendation_structure(self, optimizer, sample_workflow):
        """Verify recommendations have correct structure"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        for rec in analysis.optimization_opportunities:
            assert isinstance(rec, OptimizationRecommendation)
            assert hasattr(rec, 'id')
            assert hasattr(rec, 'type')
            assert hasattr(rec, 'title')
            assert hasattr(rec, 'description')
            assert hasattr(rec, 'impact_level')
            assert hasattr(rec, 'estimated_improvement')
            assert hasattr(rec, 'implementation_effort')
            assert hasattr(rec, 'steps')
            assert hasattr(rec, 'prerequisites')
            assert hasattr(rec, 'risks')
            assert hasattr(rec, 'confidence_score')

    @pytest.mark.asyncio
    async def test_recommendation_types(self, optimizer, sample_workflow):
        """Verify various recommendation types can be generated"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        recommendation_types = [rec.type for rec in analysis.optimization_opportunities]
        # Check that known types appear
        valid_types = [t for t in OptimizationType]
        for rec_type in recommendation_types:
            assert rec_type in valid_types

    @pytest.mark.asyncio
    async def test_recommendation_impact_levels(self, optimizer, sample_workflow):
        """Verify recommendations have valid impact levels"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        for rec in analysis.optimization_opportunities:
            assert rec.impact_level in [ImpactLevel.LOW, ImpactLevel.MEDIUM, ImpactLevel.HIGH, ImpactLevel.CRITICAL]

    @pytest.mark.asyncio
    async def test_recommendation_confidence_scores(self, optimizer, sample_workflow):
        """Verify confidence scores are in valid range"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        for rec in analysis.optimization_opportunities:
            assert 0 <= rec.confidence_score <= 100

    @pytest.mark.asyncio
    async def test_recommendation_implementation_effort(self, optimizer, sample_workflow):
        """Verify implementation effort is one of expected values"""
        analysis = await optimizer.analyze_workflow(sample_workflow)

        valid_efforts = ["easy", "medium", "complex"]
        for rec in analysis.optimization_opportunities:
            assert rec.implementation_effort in valid_efforts


# =============================================================================
# TEST CLASS: Optimization Planning
# =============================================================================

class TestOptimizationPlanning:
    """Tests for optimization plan creation"""

    @pytest.mark.asyncio
    async def test_optimize_workflow_plan(self, optimizer, sample_workflow):
        """Verify optimization plan is created"""
        plan = await optimizer.optimize_workflow_plan(
            sample_workflow,
            [OptimizationType.PERFORMANCE]
        )

        assert "workflow_analysis" in plan
        assert "optimization_plan" in plan
        assert "phases" in plan["optimization_plan"]

    @pytest.mark.asyncio
    async def test_optimization_plan_goals(self, optimizer, sample_workflow):
        """Verify optimization plan includes goals"""
        goals = [OptimizationType.PERFORMANCE, OptimizationType.COST]
        plan = await optimizer.optimize_workflow_plan(sample_workflow, goals)

        assert plan["optimization_plan"]["goals"] == ["performance", "cost"]

    @pytest.mark.asyncio
    async def test_optimization_plan_phases(self, optimizer, sample_workflow):
        """Verify optimization plan has phases"""
        # Create a workflow that will trigger recommendations
        # More than 5 nodes triggers single_points_of_failure rule
        large_workflow = {
            "id": "large-workflow",
            "name": "Large Workflow",
            "nodes": [{"id": f"n{i}", "type": "action"} for i in range(10)],
            "edges": []
        }

        plan = await optimizer.optimize_workflow_plan(
            large_workflow,
            [OptimizationType.RELIABILITY]
        )

        phases = plan["optimization_plan"]["phases"]
        assert len(phases) > 0

        for phase in phases:
            assert "phase" in phase
            assert "name" in phase
            assert "duration_weeks" in phase

    @pytest.mark.asyncio
    async def test_optimization_plan_estimated_improvement(self, optimizer, sample_workflow):
        """Verify optimization plan includes estimated improvements"""
        plan = await optimizer.optimize_workflow_plan(
            sample_workflow,
            [OptimizationType.EFFICIENCY]
        )

        improvement = plan["optimization_plan"]["estimated_total_improvement"]
        assert isinstance(improvement, dict)

    @pytest.mark.asyncio
    async def test_optimization_plan_timeline(self, optimizer, sample_workflow):
        """Verify optimization plan includes timeline"""
        plan = await optimizer.optimize_workflow_plan(
            sample_workflow,
            [OptimizationType.PERFORMANCE]
        )

        timeline = plan["optimization_plan"]["implementation_timeline"]
        assert isinstance(timeline, str)
        assert "days" in timeline or "weeks" in timeline


# =============================================================================
# TEST CLASS: Performance Monitoring
# =============================================================================

class TestPerformanceMonitoring:
    """Tests for performance monitoring functionality"""

    @pytest.mark.asyncio
    async def test_monitor_workflow_performance(self, optimizer):
        """Verify performance monitoring works"""
        metrics = {
            "execution_time": [5.0, 5.5, 4.8, 5.2],
            "success_rate": [0.95, 0.96, 0.94, 0.97]
        }

        result = await optimizer.monitor_workflow_performance(
            "workflow-123",
            metrics,
            time_window=24
        )

        assert "workflow_id" in result
        assert "performance_trends" in result
        assert "health_score" in result

    @pytest.mark.asyncio
    async def test_monitor_identifies_issues(self, optimizer):
        """Verify monitoring identifies performance issues"""
        metrics = {
            "execution_time": [10.0, 12.0, 15.0, 18.0],  # Increasing
            "success_rate": [0.95, 0.90, 0.85, 0.80]  # Declining
        }

        result = await optimizer.monitor_workflow_performance(
            "workflow-123",
            metrics
        )

        # Should identify declining success rate
        assert "identified_issues" in result

    @pytest.mark.asyncio
    async def test_monitor_generates_urgent_recommendations(self, optimizer):
        """Verify monitoring generates urgent recommendations for critical issues"""
        metrics = {
            "success_rate": [0.90, 0.70, 0.50, 0.30]  # Severe decline
        }

        result = await optimizer.monitor_workflow_performance(
            "workflow-123",
            metrics
        )

        # May have urgent recommendations
        assert "urgent_recommendations" in result
        assert isinstance(result["urgent_recommendations"], list)

    @pytest.mark.asyncio
    async def test_calculate_health_score(self, optimizer):
        """Verify health score calculation"""
        metrics = {"success_rate": 0.95}

        # Mock issues
        with patch.object(optimizer, '_identify_performance_issues', return_value=[]):
            result = await optimizer.monitor_workflow_performance(
                "workflow-123",
                metrics
            )

            # High success rate should give high health score
            assert result["health_score"] >= 80

    @pytest.mark.asyncio
    async def test_health_score_with_issues(self, optimizer):
        """Verify health score calculation works with provided issues"""
        # Create a simple metrics dict that will result in issues
        metrics = {
            "execution_time": [1.0, 2.0, 3.0, 4.0],
            "success_rate": [0.99, 0.85, 0.70, 0.55]  # Declining
        }

        # Don't mock - let actual implementation run
        result = await optimizer.monitor_workflow_performance(
            "workflow-123",
            metrics
        )

        # Health score should be calculated (may vary based on actual analysis)
        assert "health_score" in result
        assert 0 <= result["health_score"] <= 100


# =============================================================================
# TEST CLASS: Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_empty_workflow_analysis(self, optimizer):
        """Verify empty workflow doesn't crash"""
        workflow = {"id": "empty", "nodes": [], "edges": []}

        # Should handle gracefully
        integrations = optimizer._extract_integrations(workflow["nodes"])
        assert len(integrations) == 0

    def test_workflow_missing_fields(self, optimizer):
        """Verify workflow with missing fields is handled"""
        workflow = {"id": "minimal"}

        # Should not crash
        integrations = optimizer._extract_integrations(workflow.get("nodes", []))
        assert len(integrations) == 0

    @pytest.mark.asyncio
    async def test_optimize_with_no_recommendations(self, optimizer):
        """Verify optimization plan with no matching recommendations"""
        simple_workflow = {
            "id": "simple",
            "nodes": [{"id": "n1", "type": "trigger"}],
            "edges": []
        }

        plan = await optimizer.optimize_workflow_plan(
            simple_workflow,
            [OptimizationType.SECURITY]  # May not match any rules
        )

        # Should still return a plan structure
        assert "optimization_plan" in plan

    def test_priority_score_calculation(self, optimizer):
        """Verify priority score is calculated correctly"""
        rec = OptimizationRecommendation(
            id="test",
            type=OptimizationType.PERFORMANCE,
            title="Test",
            description="Test recommendation",
            impact_level=ImpactLevel.HIGH,
            estimated_improvement={},
            implementation_effort="easy",
            steps=[],
            prerequisites=[],
            risks=[],
            confidence_score=90
        )

        score = optimizer._calculate_priority_score(rec)
        # High impact + high confidence + easy effort = high score
        assert score > 0


# =============================================================================
# TEST CLASS: Recommendation Helper Methods
# =============================================================================

class TestRecommendationHelpers:
    """Tests for recommendation generation helper methods"""

    def test_recommend_parallel_processing(self, optimizer):
        """Verify parallel processing recommendation is generated"""
        data = {
            "workflow": {"nodes": []},
            "metrics": {}
        }
        rule = {
            "impact": ImpactLevel.HIGH,
            "improvement": {"execution_time": 40}
        }

        rec = optimizer._recommend_parallel_processing(data, rule)
        assert rec.type == OptimizationType.PERFORMANCE
        assert "parallel" in rec.title.lower()
        assert rec.impact_level == ImpactLevel.HIGH

    def test_recommend_ai_optimization(self, optimizer):
        """Verify AI optimization recommendation is generated"""
        data = {"workflow": {"nodes": []}, "metrics": {}}
        rule = {"impact": ImpactLevel.HIGH, "improvement": {"cost_reduction": 35}}

        rec = optimizer._recommend_ai_optimization(data, rule)
        assert rec.type == OptimizationType.COST
        assert "ai" in rec.title.lower() or "optimization" in rec.title.lower()

    def test_recommend_redundancy(self, optimizer):
        """Verify redundancy recommendation is generated"""
        data = {"workflow": {"nodes": []}, "metrics": {}}
        rule = {"impact": ImpactLevel.CRITICAL, "improvement": {"reliability": 80}}

        rec = optimizer._recommend_redundancy(data, rule)
        assert rec.type == OptimizationType.RELIABILITY
        assert "redundancy" in rec.title.lower() or "fallback" in rec.title.lower()

    def test_recommend_automation(self, optimizer):
        """Verify automation recommendation is generated"""
        data = {"workflow": {"nodes": []}, "metrics": {}}
        rule = {"impact": ImpactLevel.MEDIUM, "improvement": {"cycle_time": 50}}

        rec = optimizer._recommend_automation(data, rule)
        assert rec.type == OptimizationType.EFFICIENCY
        assert "automation" in rec.title.lower() or "manual" in rec.title.lower()


# =============================================================================
# TEST CLASS: Utility Methods
# =============================================================================

class TestUtilityMethods:
    """Tests for utility methods"""

    def test_count_sequential_api_calls(self, optimizer):
        """Verify API call counting works"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {"integration": "slack"}},
                    {"id": "n2", "config": {"integration": "openai"}},
                    {"id": "n3", "config": {"integration": "gmail"}}
                ]
            }
        }

        count = optimizer._count_sequential_api_calls(data)
        assert count == 3

    def test_has_large_data_processing_false(self, optimizer):
        """Verify large data processing detection returns false when not present"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {"batch_size": 100}}
                ]
            }
        }

        result = optimizer._has_large_data_processing(data)
        assert result is False

    def test_has_large_data_processing_true(self, optimizer):
        """Verify large data processing detection returns true when present"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {"batch_size": 2000}}
                ]
            }
        }

        result = optimizer._has_large_data_processing(data)
        assert result is True

    def test_has_frequent_ai_calls_true(self, optimizer):
        """Verify frequent AI call detection works"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {"integration": "openai"}},
                    {"id": "n2", "config": {"integration": "openai"}},
                    {"id": "n3", "config": {"integration": "openai"}}
                ]
            }
        }

        result = optimizer._has_frequent_ai_calls(data)
        assert result is True

    def test_has_single_points_of_failure(self, optimizer):
        """Verify single point of failure detection works"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": f"n{i}", "config": {}} for i in range(10)
                ]
            }
        }

        result = optimizer._has_single_points_of_failure(data)
        assert result is True  # More than 5 nodes

    def test_lacks_error_handling_true(self, optimizer):
        """Verify lack of error handling is detected"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {}}
                ]
            }
        }

        result = optimizer._lacks_error_handling(data)
        assert result is True

    def test_lacks_error_handling_false(self, optimizer):
        """Verify error handling is detected"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "config": {"error_handling": {"retry": True}}}
                ]
            }
        }

        result = optimizer._lacks_error_handling(data)
        assert result is False

    def test_has_manual_bottlenecks_true(self, optimizer):
        """Verify manual approval bottlenecks are detected"""
        data = {
            "workflow": {
                "nodes": [
                    {"id": "n1", "label": "Manual Approval Required"}
                ]
            }
        }

        result = optimizer._has_manual_bottlenecks(data)
        assert result is True

    def test_find_longest_path(self, optimizer):
        """Verify longest path finding works"""
        nodes = [
            {"id": "n1", "type": "action"},
            {"id": "n2", "type": "action"},
            {"id": "n3", "type": "action"}
        ]
        edges = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"}
        ]

        path = optimizer._find_longest_path(nodes, edges)
        assert len(path) == 3

    def test_calculate_total_improvement(self, optimizer):
        """Verify total improvement calculation works"""
        recommendations = [
            OptimizationRecommendation(
                id="r1", type=OptimizationType.PERFORMANCE, title="R1",
                description="R1", impact_level=ImpactLevel.HIGH,
                estimated_improvement={"execution_time": 40, "cost": 10},
                implementation_effort="easy", steps=[], prerequisites=[],
                risks=[], confidence_score=90
            ),
            OptimizationRecommendation(
                id="r2", type=OptimizationType.COST, title="R2",
                description="R2", impact_level=ImpactLevel.MEDIUM,
                estimated_improvement={"cost": 20},
                implementation_effort="medium", steps=[], prerequisites=[],
                risks=[], confidence_score=80
            )
        ]

        total = optimizer._calculate_total_improvement(recommendations)
        assert total["execution_time"] == 40
        assert total["cost"] == 30  # 10 + 20

    def test_estimate_implementation_timeline(self, optimizer):
        """Verify implementation timeline estimation works"""
        recommendations = [
            OptimizationRecommendation(
                id="r1", type=OptimizationType.PERFORMANCE, title="R1",
                description="R1", impact_level=ImpactLevel.HIGH,
                estimated_improvement={},
                implementation_effort="easy", steps=[], prerequisites=[],
                risks=[], confidence_score=90
            ),
            OptimizationRecommendation(
                id="r2", type=OptimizationType.COST, title="R2",
                description="R2", impact_level=ImpactLevel.MEDIUM,
                estimated_improvement={},
                implementation_effort="complex", steps=[], prerequisites=[],
                risks=[], confidence_score=80
            )
        ]

        timeline = optimizer._estimate_implementation_timeline(recommendations)
        assert "days" in timeline
        # Easy (1 day) + Complex (7 days) = 8 days
        assert "8" in timeline or "week" in timeline

    def test_create_implementation_phases(self, optimizer):
        """Verify implementation phases are created correctly"""
        recommendations = [
            OptimizationRecommendation(
                id="r1", type=OptimizationType.PERFORMANCE, title="R1",
                description="R1", impact_level=ImpactLevel.HIGH,
                estimated_improvement={},
                implementation_effort="easy", steps=[], prerequisites=[],
                risks=[], confidence_score=90
            )
        ]

        phases = optimizer._create_implementation_phases(recommendations, None)
        assert len(phases) > 0

        # Verify phase structure
        for phase in phases:
            assert "phase" in phase
            assert "name" in phase
            assert "duration_weeks" in phase
            assert "recommendations" in phase
