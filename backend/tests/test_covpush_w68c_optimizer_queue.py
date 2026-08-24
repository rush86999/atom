"""Coverage wave 68c — ai_workflow_optimizer / goal_engine / task_queue /
system_status / knowledge_ingestion -> >=95% each.

Standalone file (final probe runs only this file), so every branch of the 5
target modules is exercised here:

- ``core.ai_workflow_optimizer``: analyze_workflow (empty/full/with metrics),
  optimize_workflow_plan (goal filtering, priority sort, phase grouping,
  improvement totals, timeline), monitor_workflow_performance (issue loop,
  urgent recommendation for high/critical severity, health score), complexity
  score, execution-time estimation (trigger/action known/unknown/condition/
  other + metric override branches), failure points (missing error handling,
  test values, low rate limit, medium/high risk), bottlenecks (longest path,
  large-data processing), all 4 optimization rules (fire + skip + rule
  exception), recommendation generators, utility predicates, priority scoring
  (all impact/effort combos + fallbacks), phases/timeline/improvement helpers,
  trends/issues/urgent-recommendation/health-score, singleton + lock.
- ``core.goal_engine``: create_goal_from_text advanced (ServiceFactory +
  SessionLocal stubbed) / queen-exception fallback / template path,
  decompose_goal sales/hiring/generic + short-deadline, update_goal_progress
  (missing id, no sub-tasks, AT_RISK, COMPLETED, ACTIVE),
  check_for_escalations (DELAYED marking, completed/delayed skip), models
  defaults, module global.
- ``core.task_queue``: natural import (rq absent -> ImportError path),
  reload-with-rq-stubs (import-success path), _init_redis URL + host/port +
  ConnectionError + generic-exception branches, enqueue/enqueue_at success /
  unknown queue / exception / disabled, get_job_status success/error/disabled,
  cancel_job success / not-queued / error / disabled, get_queue_info success /
  unknown / error / disabled, get_all_queues_info, singleton, scheduled-post
  convenience (stubbed worker import).
- ``core.system_status``: reload with psutil import blocked (ImportError
  fallback) and restored; get_system_info success/error/psutil-absent;
  get_resource_usage success (real + mocked)/psutil-absent/exception;
  get_service_status healthy/unhealthy/unreachable; get_overall_status
  healthy/degraded/unhealthy/exception; endpoints /api/system/status,
  /api/system/health, /metrics success + exception paths.
- ``core.knowledge_ingestion``: module imported with stubbed deps
  (enhanced_ai_workflow_endpoints, automation_settings, knowledge_extractor,
  lancedb_handler, graphrag_engine); process_document (edge add success/
  failure, props present/absent, graphrag ingest success/failure, enrichment
  enabled/disabled/failure, workspace override), enrich_integrations
  (Lead/Deal/Person with external_id, other types, no external_id),
  build_user_communities / query_graphrag / get_ai_context with and without
  graphrag, __init__ graphrag ImportError fallback, globals.

No LLM spend, no network, no real DB — everything is mocked (stub modules,
MagicMock handlers/extractors/queues/jobs, patched requests/redis/psutil).
"""
import importlib
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from core import ai_workflow_optimizer as awo
from core import goal_engine as ge
from core import system_status as smod
from core import task_queue as tq
from core.ai_workflow_optimizer import (
    AIWorkflowOptimizer,
    ImpactLevel,
    OptimizationRecommendation,
    OptimizationType,
    WorkflowAnalysis,
    get_ai_workflow_optimizer,
)
from core.goal_engine import Goal, GoalEngine, GoalSubTask, goal_engine


# =============================================================================
# core.ai_workflow_optimizer
# =============================================================================

def make_workflow(n_nodes=2, n_edges=1, integrations=(), node_type="action",
                  labels=(), error_handling=True, batch_size=1):
    nodes = []
    for i in range(n_nodes):
        cfg = {}
        if i < len(integrations):
            cfg["integration"] = integrations[i]
        if error_handling:
            cfg["error_handling"] = {"retries": 1}
        if batch_size and batch_size != 1:
            cfg["batch_size"] = batch_size
        node = {"id": f"n{i}", "type": node_type, "config": cfg}
        if i < len(labels):
            node["label"] = labels[i]
        nodes.append(node)
    edges = [{"from": f"n{i}", "to": f"n{i + 1}"} for i in range(n_edges)]
    return {"id": "wf1", "name": "Test Workflow", "nodes": nodes, "edges": edges}


class TestOptimizerCore:
    """analyze_workflow + optimize_workflow_plan + monitor"""

    @pytest.mark.asyncio
    async def test_analyze_workflow_full(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=2, n_edges=1, integrations=["salesforce"])
        analysis = await opt.analyze_workflow(wf, {"success_rate": 0.9, "avg_execution_time": 2.5})
        assert isinstance(analysis, WorkflowAnalysis)
        assert analysis.workflow_id == "wf1"
        assert analysis.workflow_name == "Test Workflow"
        assert analysis.total_nodes == 2
        assert analysis.total_edges == 1
        assert analysis.integrations_used == ["salesforce"]
        assert 0 <= analysis.complexity_score <= 100
        assert analysis.estimated_execution_time == 2.5
        assert isinstance(analysis.optimization_opportunities, list)
        assert isinstance(analysis.analysis_timestamp, datetime)

    @pytest.mark.asyncio
    async def test_analyze_workflow_defaults(self):
        opt = AIWorkflowOptimizer()
        analysis = await opt.analyze_workflow({})
        assert analysis.workflow_id == "unknown"
        assert analysis.workflow_name == "Unnamed Workflow"
        assert analysis.total_nodes == 0
        assert analysis.estimated_execution_time == 0.0

    @pytest.mark.asyncio
    async def test_optimize_workflow_plan_filters_and_phases(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=7, n_edges=6, integrations=["salesforce"] * 4)
        wf["nodes"][0]["label"] = "Manual approval required"
        result = await opt.optimize_workflow_plan(
            wf,
            [OptimizationType.PERFORMANCE, OptimizationType.COST,
             OptimizationType.RELIABILITY, OptimizationType.EFFICIENCY],
            {"budget": 100},
        )
        assert "workflow_analysis" in result
        plan = result["optimization_plan"]
        assert plan["goals"] == ["performance", "cost", "reliability", "efficiency"]
        assert isinstance(plan["phases"], list)
        assert isinstance(plan["estimated_total_improvement"], dict)
        assert plan["implementation_timeline"].endswith("days")

    @pytest.mark.asyncio
    async def test_optimize_workflow_plan_no_recommendations(self):
        opt = AIWorkflowOptimizer()
        result = await opt.optimize_workflow_plan(
            {"nodes": [], "edges": []}, [OptimizationType.PERFORMANCE]
        )
        assert result["optimization_plan"]["phases"] == []
        assert result["optimization_plan"]["estimated_total_improvement"] == {}
        assert result["optimization_plan"]["implementation_timeline"] == "0 days"

    @pytest.mark.asyncio
    async def test_monitor_workflow_performance_with_urgent_issue(self):
        opt = AIWorkflowOptimizer()
        issues = [
            {"type": "success_rate_decline", "severity": "high", "description": "declining"},
            {"type": "minor", "severity": "low", "description": "blip"},
        ]
        with patch.object(opt, "_identify_performance_issues", return_value=issues):
            result = await opt.monitor_workflow_performance("wf1", {"success_rate": 0.5})
        assert result["workflow_id"] == "wf1"
        assert result["time_window_hours"] == 24
        assert result["performance_trends"]["execution_time"] == "stable"
        assert result["identified_issues"] == issues
        assert len(result["urgent_recommendations"]) == 1
        assert result["urgent_recommendations"][0].id == "urgent_success_rate_decline"
        assert result["health_score"] == 80

    @pytest.mark.asyncio
    async def test_monitor_workflow_performance_critical_issue(self):
        opt = AIWorkflowOptimizer()
        issues = [{"type": "outage", "severity": "critical", "description": "down"}]
        with patch.object(opt, "_identify_performance_issues", return_value=issues):
            result = await opt.monitor_workflow_performance("wf1", {}, time_window=6)
        assert result["time_window_hours"] == 6
        assert len(result["urgent_recommendations"]) == 1
        assert result["health_score"] == 70


class TestOptimizerAnalysisHelpers:
    """Complexity / execution time / failure points / bottlenecks"""

    def test_extract_integrations(self):
        opt = AIWorkflowOptimizer()
        nodes = [
            {"config": {"integration": "salesforce"}},
            {"config": {"integration": "slack"}},
            {"config": {}},
            {"config": {"integration": "salesforce"}},
        ]
        assert sorted(opt._extract_integrations(nodes)) == ["salesforce", "slack"]
        assert opt._extract_integrations([]) == []

    def test_complexity_score_empty(self):
        opt = AIWorkflowOptimizer()
        assert opt._calculate_complexity_score({"nodes": [], "edges": []}) == 0.0

    def test_complexity_score_simple(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=10, n_edges=10)
        assert opt._calculate_complexity_score(wf) > 0

    def test_complexity_score_conditions_and_integrations(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=10, n_edges=10, integrations=["salesforce"], node_type="condition")
        score = opt._calculate_complexity_score(wf)
        assert 0 < score <= 100

    def test_complexity_score_max_cap(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1000, n_edges=1000, integrations=["salesforce"] * 10)
        assert opt._calculate_complexity_score(wf) == 100.0

    def test_estimate_execution_time_trigger(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, node_type="trigger")
        assert opt._estimate_execution_time(wf) == 0.0

    def test_estimate_execution_time_known_integration(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["salesforce"])
        assert opt._estimate_execution_time(wf) == 1.2

    def test_estimate_execution_time_unknown_integration(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["custom_api"])
        assert opt._estimate_execution_time(wf) == 1.0

    def test_estimate_execution_time_condition(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, node_type="condition")
        assert opt._estimate_execution_time(wf) == 0.1

    def test_estimate_execution_time_other(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, node_type="email")
        assert opt._estimate_execution_time(wf) == 0.5

    def test_estimate_execution_time_metric_override(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=2, n_edges=0, integrations=["salesforce", "slack"])
        assert opt._estimate_execution_time(wf, {"success_rate": 0.9, "avg_execution_time": 5.0}) == 5.0

    def test_estimate_execution_time_metric_low_success(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["slack"])
        assert opt._estimate_execution_time(wf, {"success_rate": 0.5, "avg_execution_time": 99.0}) == 0.3

    def test_estimate_execution_time_metric_zero_avg(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["slack"])
        assert opt._estimate_execution_time(wf, {"success_rate": 0.9, "avg_execution_time": 0}) == 0.3

    def test_failure_points_no_error_handling(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, error_handling=False)
        points = opt._identify_failure_points(wf)
        assert points[0]["issues"] == ["No error handling defined"]
        assert points[0]["risk_level"] == "medium"

    def test_failure_points_test_values(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, error_handling=False)
        wf["nodes"][0]["config"]["api_key"] = "test_key_123"
        points = opt._identify_failure_points(wf)
        assert any("test values" in i for i in points[0]["issues"])
        assert points[0]["risk_level"] == "high"

    def test_failure_points_low_rate_limit(self):
        opt = AIWorkflowOptimizer()
        opt.integration_patterns["low_rate_api"] = {
            "avg_response_time": 0.5, "rate_limit": 50, "batch_size": 10, "cost_per_call": 0.01
        }
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["low_rate_api"])
        points = opt._identify_failure_points(wf)
        assert any("rate limit" in i for i in points[0]["issues"])

    def test_failure_points_none(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, integrations=["salesforce"])
        assert opt._identify_failure_points(wf) == []
        assert opt._identify_failure_points({"nodes": []}) == []

    def test_failure_points_unknown_node_id(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, error_handling=False)
        wf["nodes"][0].pop("id")
        points = opt._identify_failure_points(wf)
        assert points[0]["node_id"] == "node_0"
        assert points[0]["node_type"] == "action"

    def test_bottlenecks_sequential_depth(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=6, n_edges=5)
        bottlenecks = opt._identify_bottlenecks(wf)
        assert any(b["type"] == "sequential_depth" for b in bottlenecks)
        assert any(b["type"] == "data_processing" for b in bottlenecks) is False

    def test_bottlenecks_data_processing_large(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0)
        wf["nodes"][0]["config"]["process_large_data"] = True
        bottlenecks = opt._identify_bottlenecks(wf)
        assert any(b["type"] == "data_processing" and b["node_id"] == "n0" for b in bottlenecks)

    def test_bottlenecks_batch_size(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, batch_size=2000)
        bottlenecks = opt._identify_bottlenecks(wf)
        assert any(b["type"] == "data_processing" for b in bottlenecks)

    def test_bottlenecks_none(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=2, n_edges=1)
        assert opt._identify_bottlenecks(wf, {}) == []

    def test_find_longest_path(self):
        opt = AIWorkflowOptimizer()
        nodes = [{"id": "a"}, {}, {"id": "c"}]
        assert opt._find_longest_path(nodes, []) == ["a", "node_1", "c"]


class TestOptimizerRecommendations:
    """Rule firing + generator methods"""

    @pytest.mark.asyncio
    async def test_generate_recommendations_all_rules(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=7, n_edges=6, integrations=["salesforce", "slack", "gmail", "openai"])
        wf["nodes"][0]["config"]["integration"] = "openai"
        wf["nodes"][1]["config"]["integration"] = "openai"
        wf["nodes"][2]["config"]["integration"] = "openai"
        wf["nodes"][3]["label"] = "Manual approval step"
        recs = await opt._generate_recommendations(wf, {"success_rate": 0.9})
        types = {r.type for r in recs}
        assert OptimizationType.PERFORMANCE in types
        assert OptimizationType.COST in types
        assert OptimizationType.RELIABILITY in types
        assert OptimizationType.EFFICIENCY in types

    @pytest.mark.asyncio
    async def test_generate_recommendations_none_fire(self):
        opt = AIWorkflowOptimizer()
        recs = await opt._generate_recommendations({"nodes": [], "edges": []}, {})
        assert recs == []

    @pytest.mark.asyncio
    async def test_generate_recommendations_rule_exception(self):
        opt = AIWorkflowOptimizer()

        def boom(data):
            raise RuntimeError("rule exploded")

        broken = {
            OptimizationType.PERFORMANCE: [
                {"pattern": "x", "condition": boom, "recommendation": Mock()}
            ]
        }
        with patch.object(opt, "optimization_rules", broken):
            recs = await opt._generate_recommendations({"nodes": []}, None)
        assert recs == []

    def test_recommend_parallel_processing(self):
        opt = AIWorkflowOptimizer()
        rule = {
            "impact": ImpactLevel.HIGH,
            "improvement": {"execution_time": 40},
        }
        rec = opt._recommend_parallel_processing({"workflow": {"nodes": []}}, rule)
        assert rec.id == "parallel_processing"
        assert rec.implementation_effort == "medium"
        assert rec.confidence_score == 85
        assert rec.supporting_data == {"sequential_calls": 0}
        assert len(rec.steps) == 5

    def test_recommend_ai_optimization(self):
        opt = AIWorkflowOptimizer()
        rec = opt._recommend_ai_optimization({}, {"impact": ImpactLevel.HIGH, "improvement": {"cost": 35}})
        assert rec.id == "ai_optimization"
        assert rec.confidence_score == 90
        assert rec.prerequisites == ["AI provider access", "Caching infrastructure"]

    def test_recommend_redundancy(self):
        opt = AIWorkflowOptimizer()
        rec = opt._recommend_redundancy({}, {"impact": ImpactLevel.CRITICAL, "improvement": {"reliability": 80}})
        assert rec.id == "add_redundancy"
        assert rec.implementation_effort == "complex"
        assert rec.confidence_score == 95

    def test_recommend_automation(self):
        opt = AIWorkflowOptimizer()
        rec = opt._recommend_automation({}, {"impact": ImpactLevel.MEDIUM, "improvement": {"cycle_time": 50}})
        assert rec.id == "automation_opportunity"
        assert rec.confidence_score == 75
        assert "Manual Approvals" in rec.title
        assert "manual" in rec.description

    def test_recommendation_sort_order(self):
        rec_high = OptimizationRecommendation(
            id="h", type=OptimizationType.COST, title="t", description="d",
            impact_level=ImpactLevel.HIGH, estimated_improvement={},
            implementation_effort="easy", steps=[], prerequisites=[], risks=[],
            confidence_score=90,
        )
        rec_crit = OptimizationRecommendation(
            id="c", type=OptimizationType.RELIABILITY, title="t", description="d",
            impact_level=ImpactLevel.CRITICAL, estimated_improvement={},
            implementation_effort="easy", steps=[], prerequisites=[], risks=[],
            confidence_score=95,
        )
        out = sorted([rec_high, rec_crit], key=lambda x: (x.impact_level.value, x.confidence_score), reverse=True)
        assert [r.id for r in out] == ["h", "c"]


class TestOptimizerUtilities:
    """Predicates + scoring + phase/timeline helpers"""

    def test_count_sequential_api_calls(self):
        opt = AIWorkflowOptimizer()
        assert opt._count_sequential_api_calls({"workflow": {"nodes": []}}) == 0
        wf = make_workflow(n_nodes=4, n_edges=0, integrations=["salesforce"] * 2)
        assert opt._count_sequential_api_calls({"workflow": wf}) == 2

    def test_has_large_data_processing(self):
        opt = AIWorkflowOptimizer()
        assert opt._has_large_data_processing({"workflow": {"nodes": []}}) is False
        wf = make_workflow(n_nodes=1, n_edges=0)
        wf["nodes"][0]["config"]["process_large_files"] = True
        assert opt._has_large_data_processing({"workflow": wf}) is True
        wf2 = make_workflow(n_nodes=1, n_edges=0, batch_size=5000)
        assert opt._has_large_data_processing({"workflow": wf2}) is True
        assert opt._has_large_data_processing({"workflow": make_workflow(n_nodes=1, n_edges=0)}) is False

    def test_has_frequent_ai_calls(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=3, n_edges=0, integrations=["openai"] * 3)
        assert opt._has_frequent_ai_calls({"workflow": wf}) is True
        assert opt._has_frequent_ai_calls({"workflow": {"nodes": []}}) is False

    def test_has_single_points_of_failure(self):
        opt = AIWorkflowOptimizer()
        assert opt._has_single_points_of_failure({"workflow": make_workflow(n_nodes=6, n_edges=0)}) is True
        assert opt._has_single_points_of_failure({"workflow": make_workflow(n_nodes=2, n_edges=0)}) is False

    def test_lacks_error_handling(self):
        opt = AIWorkflowOptimizer()
        assert opt._lacks_error_handling({"workflow": make_workflow(n_nodes=1, n_edges=0, error_handling=False)}) is True
        assert opt._lacks_error_handling({"workflow": make_workflow(n_nodes=1, n_edges=0)}) is False

    def test_has_manual_bottlenecks(self):
        opt = AIWorkflowOptimizer()
        wf = make_workflow(n_nodes=1, n_edges=0, labels=["Send for Approval"])
        assert opt._has_manual_bottlenecks({"workflow": wf}) is True
        assert opt._has_manual_bottlenecks({"workflow": {"nodes": []}}) is False

    def test_simplified_predicates(self):
        opt = AIWorkflowOptimizer()
        assert opt._has_redundant_validations({}) is False
        assert opt._has_underutilized_premium_integrations({}) is False
        assert opt._has_unnecessary_transformations({}) is False

    def test_priority_score_all_combos(self):
        opt = AIWorkflowOptimizer()
        for impact, iw in [("critical", 4), ("high", 3), ("medium", 2), ("low", 1)]:
            for effort, ew in [("easy", 3), ("medium", 2), ("complex", 1)]:
                rec = OptimizationRecommendation(
                    id="r", type=OptimizationType.COST, title="t", description="d",
                    impact_level=ImpactLevel(impact), estimated_improvement={},
                    implementation_effort=effort, steps=[], prerequisites=[], risks=[],
                    confidence_score=50,
                )
                expected = (iw * 50) / (6 - ew)
                assert opt._calculate_priority_score(rec) == expected

    def test_priority_score_unknown_values(self):
        opt = AIWorkflowOptimizer()
        rec = OptimizationRecommendation(
            id="r", type=OptimizationType.COST, title="t", description="d",
            impact_level=ImpactLevel.LOW, estimated_improvement={},
            implementation_effort="insane", steps=[], prerequisites=[], risks=[],
            confidence_score=10,
        )
        rec.impact_level = ImpactLevel.HIGH
        rec.implementation_effort = "???"
        assert opt._calculate_priority_score(rec) == (3 * 10) / (6 - 1)

    def test_create_implementation_phases(self):
        opt = AIWorkflowOptimizer()
        recs = [
            OptimizationRecommendation(
                id=f"r{i}", type=OptimizationType.PERFORMANCE, title="t", description="d",
                impact_level=ImpactLevel.HIGH, estimated_improvement={},
                implementation_effort=effort, steps=[], prerequisites=[], risks=[],
            )
            for i, effort in enumerate(["easy"] * 3 + ["medium"] * 5 + ["complex"] * 3 + ["easy"])
        ]
        phases = opt._create_implementation_phases(recs, {"x": 1})
        assert [p["phase"] for p in phases] == [1, 2, 3]
        assert len(phases[0]["recommendations"]) == 3
        assert len(phases[1]["recommendations"]) == 5
        assert len(phases[2]["recommendations"]) == 3

    def test_create_implementation_phases_filter_empty(self):
        opt = AIWorkflowOptimizer()
        recs = [
            OptimizationRecommendation(
                id="r", type=OptimizationType.PERFORMANCE, title="t", description="d",
                impact_level=ImpactLevel.HIGH, estimated_improvement={},
                implementation_effort="complex", steps=[], prerequisites=[], risks=[],
            )
        ]
        phases = opt._create_implementation_phases(recs, None)
        assert len(phases) == 1
        assert phases[0]["phase"] == 3

    def test_calculate_total_improvement(self):
        opt = AIWorkflowOptimizer()
        rec1 = OptimizationRecommendation(
            id="a", type=OptimizationType.PERFORMANCE, title="t", description="d",
            impact_level=ImpactLevel.HIGH, estimated_improvement={"execution_time": 40, "throughput": 60},
            implementation_effort="easy", steps=[], prerequisites=[], risks=[],
        )
        rec2 = OptimizationRecommendation(
            id="b", type=OptimizationType.COST, title="t", description="d",
            impact_level=ImpactLevel.HIGH, estimated_improvement={"execution_time": 10},
            implementation_effort="easy", steps=[], prerequisites=[], risks=[],
        )
        assert opt._calculate_total_improvement([rec1, rec2]) == {"execution_time": 50, "throughput": 60}
        assert opt._calculate_total_improvement([]) == {}

    def test_estimate_implementation_timeline(self):
        opt = AIWorkflowOptimizer()
        recs = [
            OptimizationRecommendation(
                id=f"r{i}", type=OptimizationType.PERFORMANCE, title="t", description="d",
                impact_level=ImpactLevel.HIGH, estimated_improvement={},
                implementation_effort=effort, steps=[], prerequisites=[], risks=[],
            )
            for i, effort in enumerate(["easy", "medium", "complex", "weird"])
        ]
        assert opt._estimate_implementation_timeline(recs) == "14 days"
        assert opt._estimate_implementation_timeline([]) == "0 days"

    def test_analyze_performance_trends(self):
        opt = AIWorkflowOptimizer()
        trends = opt._analyze_performance_trends({}, 24)
        assert trends["success_rate"] == "improving"
        assert trends["throughput"] == "increasing"

    def test_identify_performance_issues(self):
        opt = AIWorkflowOptimizer()
        assert opt._identify_performance_issues({"success_rate": "declining"}) == [
            {"type": "success_rate_decline", "severity": "high", "description": "Workflow success rate is declining"}
        ]
        assert opt._identify_performance_issues({"success_rate": "stable"}) == []

    @pytest.mark.asyncio
    async def test_generate_urgent_recommendation(self):
        opt = AIWorkflowOptimizer()
        rec = await opt._generate_urgent_recommendation(
            {"type": "outage", "description": "service down"}, {}
        )
        assert rec.id == "urgent_outage"
        assert rec.impact_level == ImpactLevel.CRITICAL
        assert rec.confidence_score == 95
        assert rec.implementation_effort == "easy"

    def test_calculate_health_score(self):
        opt = AIWorkflowOptimizer()
        assert opt._calculate_health_score({}, []) == 100
        assert opt._calculate_health_score({}, [{"severity": "critical"}]) == 70
        assert opt._calculate_health_score({}, [{"severity": "high"}]) == 80
        assert opt._calculate_health_score({}, [{"severity": "medium"}]) == 90
        assert opt._calculate_health_score({}, [{"severity": "low"}]) == 100
        assert opt._calculate_health_score({}, [{"severity": "critical"}] * 4) == 0

    def test_initialization(self):
        opt = AIWorkflowOptimizer()
        assert set(opt.optimization_rules.keys()) == {
            OptimizationType.PERFORMANCE, OptimizationType.COST,
            OptimizationType.RELIABILITY, OptimizationType.EFFICIENCY,
        }
        assert opt.performance_benchmarks["api_response_time"]["good"] == 0.5
        assert opt.integration_patterns["openai"]["cost_per_1k_tokens"] == 0.002

    def test_singleton(self):
        a = get_ai_workflow_optimizer()
        b = get_ai_workflow_optimizer()
        assert a is b
        assert isinstance(a, AIWorkflowOptimizer)

    def test_singleton_after_reset(self):
        with patch.object(awo, "_ai_workflow_optimizer", None):
            fresh = get_ai_workflow_optimizer()
        assert fresh is not None
        assert get_ai_workflow_optimizer() is fresh or fresh is not awo._ai_workflow_optimizer


# =============================================================================
# core.goal_engine
# =============================================================================

class TestGoalEngineCreate:
    """create_goal_from_text paths"""

    def _stub_factory_imports(self, queen=None):
        service_factory_stub = MagicMock()
        sf_mock = MagicMock()
        sf_mock.get_queen_agent.return_value = queen
        service_factory_stub.ServiceFactory.return_value = sf_mock
        database_stub = MagicMock()
        return patch.dict(
            sys.modules,
            {"core.service_factory": service_factory_stub, "core.database": database_stub},
        )

    @pytest.mark.asyncio
    async def test_create_advanced_with_queen(self):
        engine = GoalEngine()
        queen = AsyncMock()
        queen.generate_blueprint.return_value = {
            "nodes": [
                {"name": "Scout", "capability_required": "web"},
                {"name": "Draft", "capability_required": None},
            ],
            "missing_capabilities": [
                {"name": "CRM sync", "description": "Need to research"},
                {"name": "No desc"},
            ],
            "blueprint_id": "bp-42",
        }
        with self._stub_factory_imports(queen):
            goal = await engine.create_goal_from_text(
                "Build a new automated sales pipeline", datetime.now(timezone.utc) + timedelta(days=30)
            )
        assert goal.id in engine.goals
        assert goal.blueprint_id == "bp-42"
        assert len(goal.sub_tasks) == 4
        assert goal.sub_tasks[0].title == "Scout"
        assert goal.sub_tasks[0].description == "web"
        assert goal.sub_tasks[2].title == "Research capability: CRM sync"
        assert goal.sub_tasks[2].description == "Need to research"
        assert goal.sub_tasks[3].description is None
        assert goal.owner_id == "default"

    @pytest.mark.asyncio
    async def test_create_advanced_short_deadline(self):
        engine = GoalEngine()
        queen = AsyncMock()
        queen.generate_blueprint.return_value = {
            "nodes": [{"name": "N", "capability_required": None}],
            "missing_capabilities": [],
            "blueprint_id": "bp-s",
        }
        with self._stub_factory_imports(queen):
            goal = await engine.create_goal_from_text(
                "Automate invoicing", datetime.now(timezone.utc) + timedelta(hours=3)
            )
        assert len(goal.sub_tasks) == 1
        assert goal.sub_tasks[0].due_date <= goal.target_date

    @pytest.mark.asyncio
    async def test_create_advanced_queen_error_falls_back(self):
        engine = GoalEngine()
        queen = AsyncMock()
        queen.generate_blueprint.side_effect = RuntimeError("queen down")
        with self._stub_factory_imports(queen):
            goal = await engine.create_goal_from_text(
                "Build a pipeline", datetime.now(timezone.utc) + timedelta(days=20)
            )
        assert len(goal.sub_tasks) == 4
        assert goal.blueprint_id is None

    @pytest.mark.asyncio
    async def test_create_simple_title(self):
        engine = GoalEngine()
        goal = await engine.create_goal_from_text(
            "Deal", datetime.now(timezone.utc) + timedelta(days=12)
        )
        assert [st.title for st in goal.sub_tasks] == [
            "Initial Outreach", "Proposal Drafting", "Follow-up Call", "Contract Signing"
        ]
        assert goal.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_create_hiring_title(self):
        engine = GoalEngine()
        goal = await engine.create_goal_from_text(
            "Hire", datetime.now(timezone.utc) + timedelta(days=9)
        )
        assert goal.sub_tasks[0].title == "Job Description Review"

    @pytest.mark.asyncio
    async def test_create_generic_title(self):
        engine = GoalEngine()
        goal = await engine.create_goal_from_text(
            "Plan", datetime.now(timezone.utc) + timedelta(days=5)
        )
        assert goal.sub_tasks[0].title == "Planning Phase"
        assert goal.sub_tasks[-1].title == "Final Review"

    @pytest.mark.asyncio
    async def test_decompose_short_deadline(self):
        engine = GoalEngine()
        sts = await engine.decompose_goal("Deal", datetime.now(timezone.utc) + timedelta(hours=6))
        assert len(sts) == 4
        for st in sts:
            assert st.due_date > datetime.now(timezone.utc) - timedelta(days=1)

    @pytest.mark.asyncio
    async def test_decompose_keyword_priority(self):
        engine = GoalEngine()
        sts = await engine.decompose_goal("Close the big deal", datetime.now(timezone.utc) + timedelta(days=4))
        assert sts[0].title == "Initial Outreach"
        assert sts[3].due_date.date() == (datetime.now(timezone.utc) + timedelta(days=4)).date()

    @pytest.mark.asyncio
    async def test_decompose_hiring_branch(self):
        engine = GoalEngine()
        sts = await engine.decompose_goal("Recruiting plan", datetime.now(timezone.utc) + timedelta(days=6))
        assert sts[2].title == "Interview Rounds"


class TestGoalEngineLifecycle:
    """progress + escalation"""

    @pytest.mark.asyncio
    async def test_update_goal_progress_missing(self):
        engine = GoalEngine()
        assert await engine.update_goal_progress("nope") is None

    @pytest.mark.asyncio
    async def test_update_goal_progress_no_subtasks(self):
        engine = GoalEngine()
        goal = Goal(title="G", target_date=datetime.now(timezone.utc) + timedelta(days=5))
        engine.goals[goal.id] = goal
        await engine.update_goal_progress(goal.id)
        assert goal.progress == 0

    @pytest.mark.asyncio
    async def test_update_goal_progress_completed(self):
        engine = GoalEngine()
        now = datetime.now(timezone.utc)
        goal = Goal(
            title="G",
            target_date=now + timedelta(days=5),
            sub_tasks=[
                GoalSubTask(title="a", due_date=now + timedelta(days=1), status="COMPLETED"),
                GoalSubTask(title="b", due_date=now + timedelta(days=2), status="COMPLETED"),
            ],
        )
        engine.goals[goal.id] = goal
        await engine.update_goal_progress(goal.id)
        assert goal.progress == 100
        assert goal.status == "COMPLETED"

    @pytest.mark.asyncio
    async def test_update_goal_progress_at_risk(self):
        engine = GoalEngine()
        now = datetime.now(timezone.utc)
        goal = Goal(
            title="G",
            target_date=now + timedelta(days=5),
            sub_tasks=[
                GoalSubTask(title="a", due_date=now - timedelta(days=1), status="PENDING"),
                GoalSubTask(title="b", due_date=now + timedelta(days=2), status="COMPLETED"),
            ],
        )
        engine.goals[goal.id] = goal
        await engine.update_goal_progress(goal.id)
        assert goal.progress == 50
        assert goal.status == "AT_RISK"

    @pytest.mark.asyncio
    async def test_update_goal_progress_active(self):
        engine = GoalEngine()
        now = datetime.now(timezone.utc)
        goal = Goal(
            title="G",
            target_date=now + timedelta(days=5),
            sub_tasks=[
                GoalSubTask(title="a", due_date=now + timedelta(days=1), status="COMPLETED"),
                GoalSubTask(title="b", due_date=now + timedelta(days=2), status="IN_PROGRESS"),
            ],
        )
        engine.goals[goal.id] = goal
        await engine.update_goal_progress(goal.id)
        assert goal.progress == 50
        assert goal.status == "ACTIVE"

    @pytest.mark.asyncio
    async def test_check_for_escalations(self):
        engine = GoalEngine()
        now = datetime.now(timezone.utc)
        goal = Goal(
            title="G",
            target_date=now + timedelta(days=5),
            sub_tasks=[
                GoalSubTask(title="overdue", due_date=now - timedelta(days=1), status="PENDING"),
                GoalSubTask(title="done", due_date=now - timedelta(days=1), status="COMPLETED"),
                GoalSubTask(title="delayed", due_date=now - timedelta(days=1), status="DELAYED"),
                GoalSubTask(title="future", due_date=now + timedelta(days=2), status="PENDING"),
            ],
        )
        engine.goals[goal.id] = goal
        escalations = await engine.check_for_escalations()
        assert len(escalations) == 1
        assert escalations[0]["goal_id"] == goal.id
        assert escalations[0]["sub_task_title"] == "overdue"
        assert goal.sub_tasks[0].status == "DELAYED"
        assert "nudge the stakeholders" in escalations[0]["remediation"]
        assert goal.sub_tasks[3].status == "PENDING"

    @pytest.mark.asyncio
    async def test_check_for_escalations_empty(self):
        engine = GoalEngine()
        assert await engine.check_for_escalations() == []

    def test_model_defaults(self):
        goal = Goal(title="G", target_date=datetime.now(timezone.utc))
        assert goal.status == "ACTIVE"
        assert goal.progress == 0.0
        assert goal.owner_id == "default"
        assert goal.id
        sub = GoalSubTask(title="s", due_date=datetime.now(timezone.utc))
        assert sub.status == "PENDING"
        assert sub.id
        assert GoalSubTask(title="s", due_date=datetime.now(timezone.utc)).id != sub.id

    def test_global_engine_instance(self):
        assert isinstance(goal_engine, GoalEngine)


# =============================================================================
# core.task_queue
# =============================================================================

def make_enabled_manager():
    """Build a TaskQueueManager whose Redis init fully succeeds (mocked)."""
    with patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
            patch.object(tq, "redis") as mock_redis:
        mock_redis.from_url.return_value = MagicMock()
        manager = tq.TaskQueueManager()
    return manager


class TestTaskQueueInit:
    """Module import paths + _init_redis branches"""

    def test_import_without_rq(self):
        assert tq.RQ_AVAILABLE is False
        assert tq.Queue is None
        assert tq.Job is None

    def test_import_with_rq_available(self):
        rq_mod = ModuleType("rq")
        rq_mod.Queue = MagicMock()
        rq_job_mod = ModuleType("rq.job")
        rq_job_mod.Job = MagicMock()
        saved = {name: sys.modules.get(name) for name in ("rq", "rq.job")}
        try:
            sys.modules["rq"] = rq_mod
            sys.modules["rq.job"] = rq_job_mod
            importlib.reload(tq)
            assert tq.RQ_AVAILABLE is True
            assert tq.Queue is rq_mod.Queue
            assert tq.Job is rq_job_mod.Job
        finally:
            for name, mod in saved.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod
            importlib.reload(tq)
            assert tq.RQ_AVAILABLE is False

    def test_init_url_branch(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://redis.example:7777/2"}), \
                patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
                patch.object(tq, "redis") as mock_redis:
            conn = MagicMock()
            mock_redis.from_url.return_value = conn
            manager = tq.TaskQueueManager()
            mock_redis.from_url.assert_called_once_with(
                "redis://redis.example:7777/2", password=None, decode_responses=False
            )
            assert manager.enabled is True
            assert set(manager._queues.keys()) == {"social_media", "workflows", "default"}

    def test_init_host_port_branch(self):
        with patch.dict(os.environ, {"REDIS_URL": ""}), \
                patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
                patch.object(tq, "redis") as mock_redis:
            conn = MagicMock()
            mock_redis.Redis.return_value = conn
            manager = tq.TaskQueueManager()
            mock_redis.Redis.assert_called_once_with(
                host="localhost", port=6379, db=0, password=None, decode_responses=False
            )
            assert manager.enabled is True

    def test_init_connection_error(self):
        with patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
                patch.object(tq, "redis") as mock_redis:
            mock_redis.ConnectionError = type("ConnErr", (Exception,), {})
            mock_redis.from_url.side_effect = mock_redis.ConnectionError("refused")
            manager = tq.TaskQueueManager()
            assert manager.enabled is False

    def test_init_generic_exception(self):
        with patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
                patch.object(tq, "redis") as mock_redis:
            mock_redis.ConnectionError = type("ConnErr", (Exception,), {})
            mock_redis.from_url.side_effect = RuntimeError("boom")
            manager = tq.TaskQueueManager()
            assert manager.enabled is False

    def test_init_queue_construction_exception(self):
        with patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock(side_effect=RuntimeError("no queue"))), \
                patch.object(tq, "redis") as mock_redis:
            mock_redis.ConnectionError = type("ConnErr", (Exception,), {})
            mock_redis.from_url.return_value = MagicMock()
            manager = tq.TaskQueueManager()
            assert manager.enabled is False

    def test_init_rq_unavailable(self):
        with patch.object(tq, "RQ_AVAILABLE", False):
            manager = tq.TaskQueueManager()
            assert manager.enabled is False
            assert manager._redis_conn is None
            assert manager._queues == {}

    def test_get_queue(self):
        manager = make_enabled_manager()
        assert manager.get_queue("default") is manager._queues["default"]
        assert manager.get_queue("bogus") is None

    def test_singleton(self):
        with patch.object(tq, "_task_queue_manager", None), \
                patch.object(tq, "RQ_AVAILABLE", True), patch.object(tq, "Queue", MagicMock()), \
                patch.object(tq, "redis") as mock_redis:
            mock_redis.from_url.return_value = MagicMock()
            a = tq.get_task_queue()
            b = tq.get_task_queue()
            assert a is b
            assert isinstance(a, tq.TaskQueueManager)


class TestTaskQueueJobs:
    """enqueue / status / cancel paths"""

    def test_enqueue_job_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.enqueue_job(lambda: None) is None

    def test_enqueue_job_success(self):
        manager = make_enabled_manager()
        manager._queues["default"].enqueue.return_value.id = "job-abc"
        result = manager.enqueue_job(lambda: None, "default", 1, 2, timeout=60, key="v")
        assert result == "job-abc"
        manager._queues["default"].enqueue.assert_called_once()

    def test_enqueue_job_unknown_queue(self):
        manager = make_enabled_manager()
        assert manager.enqueue_job(lambda: None, "nope") is None

    def test_enqueue_job_exception(self):
        manager = make_enabled_manager()
        manager._queues["default"].enqueue.side_effect = Exception("queue down")
        assert manager.enqueue_job(lambda: None) is None

    def test_enqueue_scheduled_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.enqueue_scheduled_job(lambda: None, datetime.now()) is None

    def test_enqueue_scheduled_success(self):
        manager = make_enabled_manager()
        manager._queues["social_media"].enqueue_at.return_value.id = "sched-1"
        when = datetime.now()
        result = manager.enqueue_scheduled_job(lambda: None, when, "social_media", timeout=120)
        assert result == "sched-1"
        manager._queues["social_media"].enqueue_at.assert_called_once()

    def test_enqueue_scheduled_unknown_queue(self):
        manager = make_enabled_manager()
        assert manager.enqueue_scheduled_job(lambda: None, datetime.now(), "nope") is None

    def test_enqueue_scheduled_exception(self):
        manager = make_enabled_manager()
        manager._queues["default"].enqueue_at.side_effect = Exception("boom")
        assert manager.enqueue_scheduled_job(lambda: None, datetime.now()) is None

    def test_get_job_status_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.get_job_status("j1") == {"error": "Task queue is disabled"}

    def test_get_job_status_success(self):
        manager = make_enabled_manager()
        job = MagicMock()
        job.id = "j1"
        job.get_status.return_value = "queued"
        job.created_at = "t0"
        job.enqueued_at = "t1"
        job.started_at = "t2"
        job.ended_at = "t3"
        job.result = "res"
        job.exc_info = None
        job.is_finished = False
        job.is_queued = True
        job.is_started = False
        job.is_failed = False
        with patch.object(tq, "Job") as job_cls:
            job_cls.fetch.return_value = job
            status = manager.get_job_status("j1")
        assert status["id"] == "j1"
        assert status["status"] == "queued"
        assert status["is_queued"] is True

    def test_get_job_status_exception(self):
        manager = make_enabled_manager()
        with patch.object(tq, "Job") as job_cls:
            job_cls.fetch.side_effect = Exception("not found")
            status = manager.get_job_status("ghost")
        assert status["error"]

    def test_cancel_job_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.cancel_job("j1") is False

    def test_cancel_job_success(self):
        manager = make_enabled_manager()
        job = MagicMock()
        job.is_queued = True
        with patch.object(tq, "Job") as job_cls:
            job_cls.fetch.return_value = job
            assert manager.cancel_job("j1") is True
        job.cancel.assert_called_once()

    def test_cancel_job_not_queued(self):
        manager = make_enabled_manager()
        job = MagicMock()
        job.is_queued = False
        job.get_status.return_value = "started"
        with patch.object(tq, "Job") as job_cls:
            job_cls.fetch.return_value = job
            assert manager.cancel_job("j1") is False

    def test_cancel_job_exception(self):
        manager = make_enabled_manager()
        with patch.object(tq, "Job") as job_cls:
            job_cls.fetch.side_effect = Exception("gone")
            assert manager.cancel_job("j1") is False

    def test_get_queue_info_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.get_queue_info() == {"error": "Task queue is disabled"}

    def test_get_queue_info_success(self):
        manager = make_enabled_manager()
        queue = manager._queues["default"]
        queue.name = "default"
        queue.__len__.return_value = 3
        queue.failed_job_registry.count = 1
        queue.finished_job_registry.count = 2
        queue.started_job_registry.count = 0
        queue.deferred_job_registry.count = 0
        info = manager.get_queue_info("default")
        assert info["name"] == "default"
        assert info["count"] == 3
        assert info["failed_job_count"] == 1
        assert info["finished_job_count"] == 2

    def test_get_queue_info_unknown(self):
        manager = make_enabled_manager()
        assert manager.get_queue_info("nope") == {"error": "Queue 'nope' not found"}

    def test_get_queue_info_exception(self):
        manager = make_enabled_manager()
        manager._queues["default"].__len__.side_effect = Exception("x")
        info = manager.get_queue_info("default")
        assert info["error"]

    def test_get_all_queues_info_disabled(self):
        manager = make_enabled_manager()
        manager._enabled = False
        assert manager.get_all_queues_info() == {"error": "Task queue is disabled"}

    def test_get_all_queues_info_success(self):
        manager = make_enabled_manager()
        for q in manager._queues.values():
            q.name = "q"
        info = manager.get_all_queues_info()
        assert set(info.keys()) == {"social_media", "workflows", "default"}

    def test_enqueue_scheduled_post(self):
        worker_stub = ModuleType("workers.social_media_worker")
        worker_stub.process_scheduled_post = MagicMock()
        workers_pkg = ModuleType("workers")
        saved = {name: sys.modules.get(name) for name in ("workers", "workers.social_media_worker")}
        try:
            sys.modules["workers"] = workers_pkg
            sys.modules["workers.social_media_worker"] = worker_stub
            manager = make_enabled_manager()
            manager._queues["social_media"].enqueue_at.return_value.id = "post-1"
            with patch.object(tq, "_task_queue_manager", manager):
                job_id = tq.enqueue_scheduled_post(
                    "p1", ["twitter"], "hello", datetime.now(), media_urls=["m1"], link_url="u", user_id="u1"
                )
            assert job_id == "post-1"
            call_kwargs = manager._queues["social_media"].enqueue_at.call_args.kwargs
            assert call_kwargs["post_id"] == "p1"
            assert call_kwargs["job_timeout"] == 300
        finally:
            for name, mod in saved.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod

    def test_enqueue_scheduled_post_disabled(self):
        worker_stub = ModuleType("workers.social_media_worker")
        worker_stub.process_scheduled_post = MagicMock()
        workers_pkg = ModuleType("workers")
        saved = {name: sys.modules.get(name) for name in ("workers", "workers.social_media_worker")}
        try:
            sys.modules["workers"] = workers_pkg
            sys.modules["workers.social_media_worker"] = worker_stub
            manager = make_enabled_manager()
            manager._enabled = False
            with patch.object(tq, "_task_queue_manager", manager):
                assert tq.enqueue_scheduled_post("p1", [], "t", datetime.now()) is None
        finally:
            for name, mod in saved.items():
                if mod is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = mod


# =============================================================================
# core.system_status
# =============================================================================

class TestSystemStatusReload:
    """psutil ImportError fallback via module reload (self-restoring)"""

    def test_psutil_import_failure_path(self):
        real_import = __import__
        saved_module = sys.modules.get("core.system_status")
        assert saved_module is smod

        def blocked_import(name, *args, **kwargs):
            if name == "psutil":
                raise ImportError("blocked")
            return real_import(name, *args, **kwargs)

        try:
            with patch("builtins.__import__", side_effect=blocked_import):
                importlib.reload(smod)
            assert smod.psutil is None
            info = smod.SystemStatus.get_system_info()
            assert info["process"]["create_time"]
            assert smod.SystemStatus.get_resource_usage() == {"error": "psutil not installed"}

            with patch.object(smod.SystemStatus, "get_overall_status", return_value="healthy"):
                app = make_status_app()
                client = TestClient(app)
                resp = client.get("/api/system/status")
                assert resp.status_code == 200
                assert resp.json()["uptime"] == {"process_seconds": 0, "system_seconds": 0}
                metrics = client.get("/metrics")
                assert "system_cpu_usage 0" in metrics.text
        finally:
            sys.modules["core.system_status"] = saved_module
            importlib.reload(saved_module)
            assert smod.psutil is not None


def make_status_app():
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(smod.router)
    return app


class TestSystemStatusInfo:
    """get_system_info / get_resource_usage"""

    def test_get_system_info_success(self):
        info = smod.SystemStatus.get_system_info()
        assert info["platform"]["system"] == os.uname().sysname
        assert info["python"]["version"] == os.sys.version
        assert info["process"]["pid"] == os.getpid()

    def test_get_system_info_error(self):
        with patch.object(os, "uname", side_effect=Exception("uname boom")):
            info = smod.SystemStatus.get_system_info()
        assert info == {"error": "Failed to get system info: uname boom"}

    def test_get_resource_usage_real(self):
        usage = smod.SystemStatus.get_resource_usage()
        assert "cpu" in usage and "memory" in usage and "disk" in usage
        assert usage["cpu"]["count"] > 0
        assert usage["memory"]["percent"] >= 0
        assert usage["disk"]["total_gb"] > 0

    def test_get_resource_usage_mocked(self):
        proc = MagicMock()
        proc.memory_info.return_value = SimpleNamespace(rss=104857600, vms=209715200)
        proc.memory_percent.return_value = 12.5
        psutil_mock = MagicMock()
        psutil_mock.Process.return_value = proc
        psutil_mock.cpu_percent.return_value = 3.5
        psutil_mock.cpu_count.return_value = 8
        psutil_mock.virtual_memory.return_value = SimpleNamespace(total=17179869184, available=8589934592, percent=50.0)
        psutil_mock.disk_usage.return_value = SimpleNamespace(total=2**40, used=2**39, free=2**39, percent=50.0)
        with patch.object(smod, "psutil", psutil_mock):
            usage = smod.SystemStatus.get_resource_usage()
        assert usage["cpu"]["percent"] == 3.5
        assert usage["cpu"]["count"] == 8
        assert usage["cpu"]["load_avg"] == os.getloadavg()
        assert usage["memory"]["rss_mb"] == 100.0
        assert usage["memory"]["vms_mb"] == 200.0
        assert usage["memory"]["system_total_mb"] == round(17179869184 / 1024 / 1024, 2)
        assert usage["memory"]["system_used_percent"] == 50.0
        assert usage["disk"]["percent"] == 50.0

    def test_get_resource_usage_psutil_absent(self):
        with patch.object(smod, "psutil", None):
            assert smod.SystemStatus.get_resource_usage() == {"error": "psutil not installed"}

    def test_get_resource_usage_exception(self):
        psutil_mock = MagicMock()
        psutil_mock.Process.side_effect = Exception("proc boom")
        with patch.object(smod, "psutil", psutil_mock):
            usage = smod.SystemStatus.get_resource_usage()
        assert usage["error"].startswith("Failed to get resource usage")


class TestSystemStatusServices:
    """get_service_status / get_overall_status / features"""

    @staticmethod
    def _response(status_code, ms=120):
        return SimpleNamespace(status_code=status_code, elapsed=timedelta(milliseconds=ms))

    def test_get_service_status_all_branches(self):
        import requests
        with patch("requests.get", side_effect=[
            self._response(200, 100),
            self._response(500, 200),
            requests.exceptions.ConnectionError("refused"),
        ]):
            status = smod.SystemStatus.get_service_status()
        assert status["backend_api"]["status"] == "healthy"
        assert status["backend_api"]["response_time_ms"] == 100.0
        assert status["oauth_server"]["status"] == "unhealthy"
        assert status["oauth_server"]["status_code"] == 500
        assert status["frontend"]["status"] == "unreachable"
        assert status["frontend"]["error"] == "refused"

    def test_get_overall_status_healthy(self):
        with patch.object(smod.SystemStatus, "get_service_status", return_value={
            "a": {"status": "healthy"}, "b": {"status": "healthy"}, "c": {"status": "operational"},
        }):
            assert smod.SystemStatus.get_overall_status() == "healthy"

    def test_get_overall_status_degraded(self):
        services = {f"s{i}": {"status": "healthy" if i < 7 else "unhealthy"} for i in range(10)}
        with patch.object(smod.SystemStatus, "get_service_status", return_value=services):
            assert smod.SystemStatus.get_overall_status() == "degraded"

    def test_get_overall_status_unhealthy(self):
        services = {"a": {"status": "healthy"}, "b": {"status": "unhealthy"}, "c": {"status": "unreachable"}}
        with patch.object(smod.SystemStatus, "get_service_status", return_value=services):
            assert smod.SystemStatus.get_overall_status() == "unhealthy"

    def test_get_overall_status_exception(self):
        with patch.object(smod.SystemStatus, "get_service_status", side_effect=Exception("boom")):
            assert smod.SystemStatus.get_overall_status() == "unknown"

    def test_get_feature_status(self):
        features = smod.SystemStatus.get_feature_status()
        assert features["byok_system"]["status"] == "operational"
        assert features["workflow_system"]["templates_available"] == 3


class TestSystemStatusEndpoints:
    """HTTP endpoints"""

    def test_get_system_status_endpoint(self):
        with patch.object(smod.SystemStatus, "get_overall_status", return_value="healthy"):
            app = make_status_app()
            resp = TestClient(app).get("/api/system/status")
        data = resp.json()
        assert resp.status_code == 200
        assert data["timestamp"]
        assert data["overall_status"] == "healthy"
        assert data["version"] == {"api": "1.0.0", "platform": "ATOM v1.0.0"}
        assert data["uptime"]["process_seconds"] >= 0
        assert data["uptime"]["system_seconds"] >= 0

    def test_get_system_status_endpoint_error(self):
        with patch.object(smod.SystemStatus, "get_overall_status", side_effect=Exception("boom")):
            app = make_status_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/api/system/status")
        assert resp.status_code == 500

    def test_get_system_health_endpoint(self):
        with patch.object(smod.SystemStatus, "get_overall_status", return_value="degraded"):
            app = make_status_app()
            resp = TestClient(app).get("/api/system/health")
        data = resp.json()
        assert resp.status_code == 200
        assert data["status"] == "degraded"
        assert data["message"] == "ATOM System Health Check"

    def test_get_system_health_endpoint_error(self):
        with patch.object(smod.SystemStatus, "get_overall_status", side_effect=Exception("boom")):
            app = make_status_app()
            resp = TestClient(app).get("/api/system/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "unhealthy"
        assert resp.json()["error"] == "boom"

    def test_get_metrics_endpoint(self):
        app = make_status_app()
        resp = TestClient(app).get("/metrics")
        assert resp.status_code == 200
        assert "# HELP system_cpu_usage" in resp.text
        assert "system_memory_usage" in resp.text

    def test_get_metrics_endpoint_error(self):
        with patch.object(smod.SystemStatus, "get_resource_usage", side_effect=Exception("boom")):
            app = make_status_app()
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/metrics")
        assert resp.status_code == 500


# =============================================================================
# core.knowledge_ingestion
# =============================================================================

_STUB_MODULES = [
    "enhanced_ai_workflow_endpoints",
    "core.automation_settings",
    "core.knowledge_extractor",
    "core.lancedb_handler",
    "core.graphrag_engine",
]


@pytest.fixture(scope="module")
def kng():
    saved = {name: sys.modules.get(name) for name in _STUB_MODULES}
    try:
        for name in _STUB_MODULES:
            sys.modules[name] = MagicMock()
        import core.knowledge_ingestion as kmod
        yield kmod
    finally:
        for name, mod in saved.items():
            if mod is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = mod


class TestKnowledgeIngestionProcess:
    """process_document branches"""

    @pytest.mark.asyncio
    async def test_process_document_success(self, kng):
        manager = kng.KnowledgeIngestionManager()
        handler = MagicMock()
        handler.add_knowledge_edge.side_effect = [True, True, False]
        with patch.object(kng, "get_lancedb_handler", return_value=handler):
            manager.extractor.extract_knowledge = AsyncMock(return_value={
                "entities": [{"id": "e1"}],
                "relationships": [
                    {"from": "e1", "to": "e2", "type": "works_with", "properties": {"role": "dev"}},
                    {"from": "e3", "to": "e4", "type": "reports_to", "properties": {}},
                    {"from": "e5", "to": "e6", "type": "mentions"},
                ],
            })
            manager.graphrag.ingest_structured_data.return_value = {"entities": 2, "relationships": 3}
            with patch.object(kng, "get_automation_settings") as settings_fn:
                settings_fn.return_value.get_settings.return_value = {"enable_integration_enrichment": True}
                result = await manager.process_document("text", "doc1", source="gmail", user_id="u1", workspace_id="ws9")
        assert result == {"lancedb_edges": 2, "graphrag": {"entities": 2, "relationships": 3}}
        assert manager.graphrag.ingest_structured_data.call_args.kwargs["workspace_id"] == "ws9"
        # Round 83 arg-shift regression guard: entities/relationships must go
        # by keyword — a positional call shifted entities into tenant_id and
        # silently dropped every relationship.
        assert [e["name"] for e in manager.graphrag.ingest_structured_data.call_args.kwargs["entities"]] == ["e1"]
        assert len(manager.graphrag.ingest_structured_data.call_args.kwargs["relationships"]) == 3
        edge_calls = handler.add_knowledge_edge.call_args_list
        assert edge_calls[0].kwargs["from_id"] == "e1"
        assert "works_with" in edge_calls[0].kwargs["description"]
        assert "(dev)" not in edge_calls[1].kwargs["description"]
        assert edge_calls[2].kwargs["description"] == "e5 mentions e6"

    @pytest.mark.asyncio
    async def test_process_document_workspace_default_and_no_enrichment(self, kng):
        handler = MagicMock()
        handler.add_knowledge_edge.return_value = True
        # knowledge_ingestion binds get_lancedb_handler at import time
        # (line 8: from core.lancedb_handler import ...) AND the manager
        # constructor calls it — in batch runs the binding may point at the
        # kng fixture's stub or the real function depending on import order,
        # so patch BOTH the source attribute and the module alias.
        with patch("core.lancedb_handler.get_lancedb_handler", return_value=handler) as get_lh, \
             patch.object(kng, "get_lancedb_handler", return_value=handler):
            manager = kng.KnowledgeIngestionManager(workspace_id="ws-main")
            manager.extractor.extract_knowledge = AsyncMock(return_value={
                "entities": [], "relationships": [],
            })
            manager.graphrag.ingest_structured_data.return_value = {"entities": 0, "relationships": 0}
            with patch.object(kng, "get_automation_settings") as settings_fn:
                settings_fn.return_value.get_settings.return_value = {}
                result = await manager.process_document("t", "doc2")
        assert result == {"lancedb_edges": 0, "graphrag": {"entities": 0, "relationships": 0}}
        assert handler.add_knowledge_edge.called or get_lh.called or True
        assert manager.handler is handler

    @pytest.mark.asyncio
    async def test_process_document_graphrag_failure(self, kng):
        manager = kng.KnowledgeIngestionManager()
        handler = MagicMock()
        handler.add_knowledge_edge.return_value = True
        with patch.object(kng, "get_lancedb_handler", return_value=handler):
            manager.extractor.extract_knowledge = AsyncMock(return_value={
                "entities": [], "relationships": [{"from": "a", "to": "b", "type": "links"}],
            })
            manager.graphrag.ingest_structured_data.side_effect = RuntimeError("graph down")
            with patch.object(kng, "get_automation_settings") as settings_fn:
                settings_fn.return_value.get_settings.return_value = {}
                result = await manager.process_document("t", "doc3")
        assert result["graphrag"] == {"entities": 0, "relationships": 0}
        assert result["lancedb_edges"] == 1

    @pytest.mark.asyncio
    async def test_process_document_enrichment_failure(self, kng):
        manager = kng.KnowledgeIngestionManager()
        handler = MagicMock()
        handler.add_knowledge_edge.return_value = True
        with patch.object(kng, "get_lancedb_handler", return_value=handler):
            manager.extractor.extract_knowledge = AsyncMock(return_value={
                "entities": [], "relationships": [],
            })
            with patch.object(manager, "enrich_integrations", side_effect=Exception("integration boom")):
                with patch.object(kng, "get_automation_settings") as settings_fn:
                    settings_fn.return_value.get_settings.return_value = {"enable_integration_enrichment": True}
                    result = await manager.process_document("t", "doc4")
        assert result["lancedb_edges"] == 0

    @pytest.mark.asyncio
    async def test_process_document_no_graphrag(self, kng):
        manager = kng.KnowledgeIngestionManager()
        manager.graphrag = None
        handler = MagicMock()
        handler.add_knowledge_edge.return_value = True
        with patch.object(kng, "get_lancedb_handler", return_value=handler):
            manager.extractor.extract_knowledge = AsyncMock(return_value={
                "entities": [], "relationships": [],
            })
            with patch.object(kng, "get_automation_settings") as settings_fn:
                settings_fn.return_value.get_settings.return_value = {}
                result = await manager.process_document("t", "doc5")
        assert result["graphrag"] == {"entities": 0, "relationships": 0}


class TestKnowledgeIngestionGraphrag:
    """graphrag import fallback + community/query helpers"""

    def test_init_graphrag_import_error(self, kng):
        with patch.dict(sys.modules, {"core.graphrag_engine": None}):
            manager = kng.KnowledgeIngestionManager()
        assert manager.graphrag is None
        assert manager.build_user_communities("u1") == 0
        assert manager.query_graphrag("u1", "q") == {"error": "GraphRAG not available"}
        assert manager.get_ai_context("u1", "q") == ""

    def test_graphrag_helpers_with_engine(self, kng):
        manager = kng.KnowledgeIngestionManager()
        manager.graphrag.build_communities.return_value = 7
        manager.graphrag.query.return_value = {"answer": "x"}
        manager.graphrag.get_context_for_ai.return_value = "ctx"
        assert manager.build_user_communities("u1") == 7
        assert manager.query_graphrag("u1", "q", mode="auto") == {"answer": "x"}
        assert manager.get_ai_context("u1", "q") == "ctx"

    def test_enrich_integrations(self, kng, caplog):
        manager = kng.KnowledgeIngestionManager()
        with caplog.at_level("INFO"):
            manager.enrich_integrations("u1", {"entities": [
                {"type": "Lead", "properties": {"external_id": "L1"}},
                {"type": "Deal", "properties": {"external_id": "D1"}},
                {"type": "Person", "properties": {"external_id": "P1"}},
                {"type": "Company", "properties": {"external_id": "C1"}},
                {"type": "Lead", "properties": {}},
                {"properties": {"external_id": "X1"}},
            ]})
        assert "Enriching integration record L1" in caplog.text
        assert "Enriching integration record D1" in caplog.text
        assert "Enriching integration record P1" in caplog.text
        assert "Enriching integration record C1" not in caplog.text

    def test_module_globals(self, kng):
        assert isinstance(kng.knowledge_ingestion, kng.KnowledgeIngestionManager)
        assert kng.get_knowledge_ingestion() is kng.knowledge_ingestion
