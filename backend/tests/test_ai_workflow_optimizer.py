"""
Test suite for ai_workflow_optimizer.py

AI-powered workflow optimization and analysis system.
Target file: backend/core/ai_workflow_optimizer.py (712 lines)
Target tests: 20-25 tests
Coverage target: 25-30%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List

# Import target module classes
from core.ai_workflow_optimizer import (
    OptimizationType,
    ImpactLevel,
    OptimizationRecommendation,
    WorkflowAnalysis,
    AIWorkflowOptimizer,
    get_ai_workflow_optimizer,
)


class TestOptimizationTypeEnum:
    """Test OptimizationType enum definition."""

    def test_performance_optimization(self):
        """OptimizationType.PERFORMANCE has correct value."""
        assert OptimizationType.PERFORMANCE.value == "performance"

    def test_cost_optimization(self):
        """OptimizationType.COST has correct value."""
        assert OptimizationType.COST.value == "cost"

    def test_reliability_optimization(self):
        """OptimizationType.RELIABILITY has correct value."""
        assert OptimizationType.RELIABILITY.value == "reliability"


class TestImpactLevelEnum:
    """Test ImpactLevel enum definition."""

    def test_low_impact(self):
        """ImpactLevel.LOW has correct value."""
        assert ImpactLevel.LOW.value == "low"

    def test_medium_impact(self):
        """ImpactLevel.MEDIUM has correct value."""
        assert ImpactLevel.MEDIUM.value == "medium"

    def test_high_impact(self):
        """ImpactLevel.HIGH has correct value."""
        assert ImpactLevel.HIGH.value == "high"

    def test_critical_impact(self):
        """ImpactLevel.CRITICAL has correct value."""
        assert ImpactLevel.CRITICAL.value == "critical"


class TestOptimizationRecommendation:
    """Test OptimizationRecommendation dataclass."""

    def test_recommendation_creation(self):
        """OptimizationRecommendation can be created with valid parameters."""
        rec = OptimizationRecommendation(
            id="rec-001",
            type=OptimizationType.PERFORMANCE,
            title="Improve Performance",
            description="Add caching to reduce API calls",
            impact_level=ImpactLevel.HIGH,
            estimated_improvement={"execution_time": 40},
            implementation_effort="medium",
            steps=["Add cache layer", "Configure TTL"],
            prerequisites=["Redis setup"],
            risks=["Cache staleness"],
            confidence_score=85
        )
        assert rec.id == "rec-001"
        assert rec.type == OptimizationType.PERFORMANCE
        assert rec.impact_level == ImpactLevel.HIGH
        assert rec.confidence_score == 85

    def test_recommendation_optional_fields(self):
        """OptimizationRecommendation handles optional workflow_section."""
        rec = OptimizationRecommendation(
            id="rec-002",
            type=OptimizationType.COST,
            title="Reduce Costs",
            description="Optimize AI usage",
            impact_level=ImpactLevel.MEDIUM,
            estimated_improvement={"cost_reduction": 35},
            implementation_effort="easy",
            steps=["Enable caching"],
            prerequisites=[],
            risks=[],
            workflow_section="ai_calls"
        )
        assert rec.workflow_section == "ai_calls"


class TestWorkflowAnalysis:
    """Test WorkflowAnalysis dataclass."""

    def test_workflow_analysis_creation(self):
        """WorkflowAnalysis can be created with valid parameters."""
        analysis = WorkflowAnalysis(
            workflow_id="wf-001",
            workflow_name="Test Workflow",
            total_nodes=10,
            total_edges=15,
            integrations_used=["slack", "gmail"],
            complexity_score=45.5,
            estimated_execution_time=5.2,
            failure_points=[],
            bottlenecks=[],
            optimization_opportunities=[],
            analysis_timestamp=datetime.now(timezone.utc)
        )
        assert analysis.workflow_id == "wf-001"
        assert analysis.total_nodes == 10
        assert analysis.complexity_score == 45.5


class TestAIWorkflowOptimizerInit:
    """Test AIWorkflowOptimizer initialization."""

    def test_optimizer_initialization(self):
        """AIWorkflowOptimizer initializes with default rules and benchmarks."""
        optimizer = AIWorkflowOptimizer()
        assert optimizer.optimization_rules is not None
        assert optimizer.performance_benchmarks is not None
        assert optimizer.integration_patterns is not None

    def test_benchmark_initialization(self):
        """AIWorkflowOptimizer initializes performance benchmarks."""
        optimizer = AIWorkflowOptimizer()
        benchmarks = optimizer.performance_benchmarks
        assert "api_response_time" in benchmarks
        assert "workflow_success_rate" in benchmarks
        assert "daily_executions" in benchmarks

    def test_integration_patterns_initialization(self):
        """AIWorkflowOptimizer initializes integration patterns."""
        optimizer = AIWorkflowOptimizer()
        patterns = optimizer.integration_patterns
        assert "salesforce" in patterns
        assert "slack" in patterns
        assert "openai" in patterns


class TestWorkflowAnalysisMethods:
    """Test workflow analysis methods."""

    @pytest.mark.asyncio
    async def test_analyze_workflow_basic(self):
        """AIWorkflowOptimizer performs basic workflow analysis."""
        optimizer = AIWorkflowOptimizer()

        workflow_data = {
            "id": "wf-001",
            "name": "Test Workflow",
            "nodes": [
                {"id": "node-1", "type": "trigger", "config": {}},
                {"id": "node-2", "type": "action", "config": {"integration": "slack"}},
                {"id": "node-3", "type": "action", "config": {"integration": "gmail"}}
            ],
            "edges": [
                {"from": "node-1", "to": "node-2"},
                {"from": "node-2", "to": "node-3"}
            ]
        }

        analysis = await optimizer.analyze_workflow(workflow_data)

        assert analysis.workflow_id == "wf-001"
        assert analysis.total_nodes == 3
        assert len(analysis.integrations_used) > 0
        assert isinstance(analysis.complexity_score, float)

    def test_extract_integrations(self):
        """AIWorkflowOptimizer extracts integrations from workflow nodes."""
        optimizer = AIWorkflowOptimizer()

        nodes = [
            {"id": "node-1", "config": {"integration": "slack"}},
            {"id": "node-2", "config": {"integration": "gmail"}},
            {"id": "node-3", "config": {}}  # No integration
        ]

        integrations = optimizer._extract_integrations(nodes)

        assert "slack" in integrations
        assert "gmail" in integrations
        assert len(integrations) == 2

    def test_calculate_complexity_score(self):
        """AIWorkflowOptimizer calculates workflow complexity score."""
        optimizer = AIWorkflowOptimizer()

        workflow_data = {
            "nodes": [
                {"id": "node-1", "type": "trigger"},
                {"id": "node-2", "type": "action"},
                {"id": "node-3", "type": "condition"}
            ],
            "edges": [
                {"from": "node-1", "to": "node-2"},
                {"from": "node-2", "to": "node-3"}
            ]
        }

        score = optimizer._calculate_complexity_score(workflow_data)

        assert 0 <= score <= 100

    def test_identify_failure_points(self):
        """AIWorkflowOptimizer identifies potential failure points."""
        optimizer = AIWorkflowOptimizer()

        workflow_data = {
            "nodes": [
                {
                    "id": "node-1",
                    "type": "action",
                    "config": {
                        "integration": "test_api",
                        "api_key": "test-key-123"  # Test value in production
                    }
                },
                {
                    "id": "node-2",
                    "type": "action",
                    "config": {}  # No error handling
                }
            ]
        }

        failure_points = optimizer._identify_failure_points(workflow_data)

        # Should identify test values as risk
        assert len(failure_points) > 0

    def test_identify_bottlenecks(self):
        """AIWorkflowOptimizer identifies performance bottlenecks."""
        optimizer = AIWorkflowOptimizer()

        # Create workflow with long sequential path
        nodes = [{"id": f"node-{i}", "type": "action", "config": {}} for i in range(7)]
        edges = [{"from": f"node-{i}", "to": f"node-{i+1}"} for i in range(6)]

        workflow_data = {"nodes": nodes, "edges": edges}

        bottlenecks = optimizer._identify_bottlenecks(workflow_data)

        # Should identify long sequential path
        assert len(bottlenecks) > 0


class TestOptimizationGeneration:
    """Test optimization recommendation generation."""

    @pytest.mark.asyncio
    async def test_generate_recommendations_parallel_processing(self):
        """AIWorkflowOptimizer generates parallel processing recommendations."""
        optimizer = AIWorkflowOptimizer()

        # Create workflow with sequential API calls
        nodes = [
            {"id": f"api-{i}", "type": "action", "config": {"integration": "api"}}
            for i in range(5)
        ]
        workflow_data = {"nodes": nodes, "edges": []}

        recommendations = await optimizer._generate_recommendations(workflow_data)

        # Should recommend parallel processing
        parallel_recs = [r for r in recommendations if r.id == "parallel_processing"]
        assert len(parallel_recs) > 0

    @pytest.mark.asyncio
    async def test_generate_recommendations_ai_optimization(self):
        """AIWorkflowOptimizer generates AI optimization recommendations."""
        optimizer = AIWorkflowOptimizer()

        # Create workflow with frequent AI calls
        nodes = [
            {"id": f"ai-{i}", "type": "action", "config": {"integration": "openai"}}
            for i in range(5)
        ]
        workflow_data = {"nodes": nodes, "edges": []}

        recommendations = await optimizer._generate_recommendations(workflow_data)

        # Should recommend AI optimization
        ai_recs = [r for r in recommendations if r.id == "ai_optimization"]
        assert len(ai_recs) > 0

    def test_recommend_parallel_processing_structure(self):
        """Parallel processing recommendation has correct structure."""
        optimizer = AIWorkflowOptimizer()

        data = {"workflow": {"nodes": [{"id": "1"}, {"id": "2"}, {"id": "3"}]}}
        rule = {
            "impact": ImpactLevel.HIGH,
            "improvement": {"execution_time": 40}
        }

        rec = optimizer._recommend_parallel_processing(data, rule)

        assert rec.type == OptimizationType.PERFORMANCE
        assert rec.impact_level == ImpactLevel.HIGH
        assert rec.estimated_improvement["execution_time"] == 40
        assert len(rec.steps) > 0
        assert rec.confidence_score > 0

    def test_recommend_ai_optimization_structure(self):
        """AI optimization recommendation has correct structure."""
        optimizer = AIWorkflowOptimizer()

        data = {"workflow": {"nodes": []}}
        rule = {
            "impact": ImpactLevel.HIGH,
            "improvement": {"cost_reduction": 35}
        }

        rec = optimizer._recommend_ai_optimization(data, rule)

        assert rec.type == OptimizationType.COST
        assert rec.estimated_improvement["cost_reduction"] == 35
        assert len(rec.prerequisites) > 0


class TestOptimizationPlanning:
    """Test optimization plan creation."""

    @pytest.mark.asyncio
    async def test_optimize_workflow_plan(self):
        """AIWorkflowOptimizer creates optimization plan."""
        optimizer = AIWorkflowOptimizer()

        workflow_data = {
            "id": "wf-001",
            "name": "Test Workflow",
            "nodes": [{"id": "node-1", "type": "action"}],
            "edges": []
        }

        plan = await optimizer.optimize_workflow_plan(
            workflow_data,
            [OptimizationType.PERFORMANCE, OptimizationType.COST]
        )

        assert "workflow_analysis" in plan
        assert "optimization_plan" in plan
        assert "goals" in plan["optimization_plan"]
        assert "phases" in plan["optimization_plan"]

    def test_create_implementation_phases(self):
        """AIWorkflowOptimizer creates phased implementation plan."""
        optimizer = AIWorkflowOptimizer()

        recommendations = [
            OptimizationRecommendation(
                id="rec-1",
                type=OptimizationType.PERFORMANCE,
                title="Easy Fix",
                description="Quick win",
                impact_level=ImpactLevel.HIGH,
                estimated_improvement={"speed": 20},
                implementation_effort="easy",
                steps=["Do it"],
                prerequisites=[],
                risks=[]
            ),
            OptimizationRecommendation(
                id="rec-2",
                type=OptimizationType.COST,
                title="Medium Fix",
                description="Moderate effort",
                impact_level=ImpactLevel.MEDIUM,
                estimated_improvement={"cost": 15},
                implementation_effort="medium",
                steps=["Plan it", "Do it"],
                prerequisites=[],
                risks=[]
            )
        ]

        phases = optimizer._create_implementation_phases(recommendations, None)

        assert len(phases) > 0
        # Should have phase names
        assert all("name" in phase for phase in phases)

    def test_calculate_priority_score(self):
        """AIWorkflowOptimizer calculates priority score correctly."""
        optimizer = AIWorkflowOptimizer()

        rec = OptimizationRecommendation(
            id="rec-1",
            type=OptimizationType.PERFORMANCE,
            title="Test",
            description="Test",
            impact_level=ImpactLevel.HIGH,
            estimated_improvement={},
            implementation_effort="easy",
            steps=[],
            prerequisites=[],
            risks=[],
            confidence_score=90
        )

        score = optimizer._calculate_priority_score(rec)

        assert score > 0


class TestPerformanceMonitoring:
    """Test workflow performance monitoring."""

    @pytest.mark.asyncio
    async def test_monitor_workflow_performance(self):
        """AIWorkflowOptimizer monitors workflow performance."""
        optimizer = AIWorkflowOptimizer()

        metrics = {
            "execution_time": [5.2, 5.5, 5.1, 5.8, 5.3],
            "success_rate": 0.95,
            "error_count": 2
        }

        monitoring = await optimizer.monitor_workflow_performance(
            "wf-001",
            metrics,
            time_window=24
        )

        assert "workflow_id" in monitoring
        assert "performance_trends" in monitoring
        assert "health_score" in monitoring

    def test_analyze_performance_trends(self):
        """AIWorkflowOptimizer analyzes performance trends."""
        optimizer = AIWorkflowOptimizer()

        metrics = {
            "execution_time": [5.0, 5.2, 5.1, 5.3, 5.2],
            "success_rate": [0.95, 0.96, 0.94, 0.97, 0.95]
        }

        trends = optimizer._analyze_performance_trends(metrics, 24)

        assert "execution_time" in trends
        assert "success_rate" in trends

    def test_calculate_health_score(self):
        """AIWorkflowOptimizer calculates workflow health score."""
        optimizer = AIWorkflowOptimizer()

        metrics = {"avg_time": 5.0}
        issues = [
            {"severity": "high"},
            {"severity": "medium"}
        ]

        health = optimizer._calculate_health_score(metrics, issues)

        assert 0 <= health <= 100
        assert health < 100  # Should be penalized for issues


class TestUtilityMethods:
    """Test utility methods."""

    def test_count_sequential_api_calls(self):
        """AIWorkflowOptimizer counts sequential API calls."""
        optimizer = AIWorkflowOptimizer()

        data = {
            "workflow": {
                "nodes": [
                    {"id": "1", "config": {"integration": "slack"}},
                    {"id": "2", "config": {"integration": "gmail"}},
                    {"id": "3", "config": {}}
                ]
            }
        }

        count = optimizer._count_sequential_api_calls(data)

        assert count == 2

    def test_has_frequent_ai_calls(self):
        """AIWorkflowOptimizer detects frequent AI calls."""
        optimizer = AIWorkflowOptimizer()

        data = {
            "workflow": {
                "nodes": [
                    {"id": "1", "config": {"provider": "openai"}},
                    {"id": "2", "config": {"provider": "openai"}},
                    {"id": "3", "config": {"provider": "openai"}}
                ]
            }
        }

        has_ai = optimizer._has_frequent_ai_calls(data)

        assert has_ai is True

    def test_has_manual_bottlenecks(self):
        """AIWorkflowOptimizer detects manual approval bottlenecks."""
        optimizer = AIWorkflowOptimizer()

        data = {
            "workflow": {
                "nodes": [
                    {"id": "1", "label": "Awaiting approval"},
                    {"id": "2", "label": "Manual review"}
                ]
            }
        }

        has_manual = optimizer._has_manual_bottlenecks(data)

        assert has_manual is True


class TestGlobalOptimizerInstance:
    """Test global optimizer instance functions."""

    def test_get_ai_workflow_optimizer_singleton(self):
        """get_ai_workflow_optimizer returns singleton instance."""
        optimizer1 = get_ai_workflow_optimizer()
        optimizer2 = get_ai_workflow_optimizer()
        assert optimizer1 is optimizer2
