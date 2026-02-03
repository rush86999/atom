"""
AI Workflow Optimization Endpoints
API endpoints for AI-powered workflow analysis and optimization
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .ai_workflow_optimizer import (
    AIWorkflowOptimizer,
    OptimizationRecommendation,
    OptimizationType,
    get_ai_workflow_optimizer,
)

router = APIRouter()

# Pydantic models for requests/responses

class WorkflowAnalysisRequest(BaseModel):
    workflow_data: Dict[str, Any]
    performance_metrics: Optional[Dict[str, Any]] = None

class OptimizationPlanRequest(BaseModel):
    workflow_data: Dict[str, Any]
    optimization_goals: List[str]  # Convert to OptimizationType enum
    constraints: Optional[Dict[str, Any]] = None

class PerformanceMonitoringRequest(BaseModel):
    workflow_id: str
    metrics: Dict[str, Any]
    time_window_hours: int = 24

# Analysis Endpoints

@router.post("/api/v1/workflows/analyze")
async def analyze_workflow(
    request: WorkflowAnalysisRequest,
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Perform comprehensive AI analysis of a workflow"""
    try:
        analysis = await optimizer.analyze_workflow(
            request.workflow_data,
            request.performance_metrics
        )

        return {
            "success": True,
            "analysis": {
                "workflow_id": analysis.workflow_id,
                "workflow_name": analysis.workflow_name,
                "metrics": {
                    "total_nodes": analysis.total_nodes,
                    "total_edges": analysis.total_edges,
                    "complexity_score": analysis.complexity_score,
                    "estimated_execution_time": analysis.estimated_execution_time,
                    "integrations_used": analysis.integrations_used
                },
                "risk_assessment": {
                    "failure_points": analysis.failure_points,
                    "bottlenecks": analysis.bottlenecks,
                    "risk_level": _calculate_risk_level(analysis)
                },
                "optimization_opportunities": len(analysis.optimization_opportunities),
                "top_recommendations": [
                    {
                        "id": rec.id,
                        "type": rec.type.value,
                        "title": rec.title,
                        "impact_level": rec.impact_level.value,
                        "estimated_improvement": rec.estimated_improvement,
                        "implementation_effort": rec.implementation_effort,
                        "confidence_score": rec.confidence_score
                    }
                    for rec in analysis.optimization_opportunities[:5]
                ]
            },
            "analyzed_at": analysis.analysis_timestamp.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Workflow analysis failed: {str(e)}"
        )

@router.post("/api/v1/workflows/optimization-plan")
async def create_optimization_plan(
    request: OptimizationPlanRequest,
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Create an AI-powered optimization plan for a workflow"""
    try:
        # Convert string goals to enum
        optimization_goals = []
        for goal in request.optimization_goals:
            try:
                optimization_goals.append(OptimizationType(goal.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid optimization goal: {goal}"
                )

        plan = await optimizer.optimize_workflow_plan(
            request.workflow_data,
            optimization_goals,
            request.constraints
        )

        return {
            "success": True,
            "optimization_plan": plan["optimization_plan"],
            "workflow_summary": {
                "id": plan["workflow_analysis"]["workflow_id"],
                "name": plan["workflow_analysis"]["workflow_name"],
                "complexity_score": plan["workflow_analysis"]["complexity_score"],
                "current_issues": len(plan["workflow_analysis"]["failure_points"])
            },
            "recommendations_by_type": _group_recommendations_by_type(
                plan["workflow_analysis"]["optimization_opportunities"]
            ),
            "generated_at": plan["generated_at"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Optimization plan creation failed: {str(e)}"
        )

@router.post("/api/v1/workflows/{workflow_id}/monitor")
async def monitor_workflow_performance(
    workflow_id: str,
    request: PerformanceMonitoringRequest,
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Monitor workflow performance and get real-time optimization suggestions"""
    try:
        # Update workflow_id if provided in request
        if request.workflow_id != workflow_id:
            request.workflow_id = workflow_id

        monitoring_result = await optimizer.monitor_workflow_performance(
            request.workflow_id,
            request.metrics,
            request.time_window_hours
        )

        return {
            "success": True,
            "monitoring_result": monitoring_result,
            "health_status": {
                "overall_health": monitoring_result["health_score"],
                "status": "healthy" if monitoring_result["health_score"] > 80 else "warning" if monitoring_result["health_score"] > 60 else "critical",
                "urgent_actions_needed": len(monitoring_result["urgent_recommendations"]),
                "issues_detected": len(monitoring_result["identified_issues"])
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Performance monitoring failed: {str(e)}"
        )

@router.get("/api/v1/workflows/{workflow_id}/recommendations")
async def get_workflow_recommendations(
    workflow_id: str,
    type_filter: Optional[str] = Query(None, description="Filter by optimization type"),
    impact_filter: Optional[str] = Query(None, description="Filter by impact level"),
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Get optimization recommendations for a workflow"""
    try:
        # In a real implementation, this would fetch stored recommendations
        # For now, we'll return a sample structure
        recommendations = [
            {
                "id": "parallel_processing",
                "type": "performance",
                "title": "Implement Parallel Processing",
                "description": "Reduce execution time by running independent operations in parallel",
                "impact_level": "high",
                "estimated_improvement": {"execution_time": 40, "throughput": 60},
                "implementation_effort": "medium",
                "steps": [
                    "Identify independent operations",
                    "Implement parallel execution pattern",
                    "Add error handling",
                    "Test performance improvements"
                ],
                "confidence_score": 85,
                "potential_risks": ["Rate limiting", "Increased complexity"]
            },
            {
                "id": "ai_cost_optimization",
                "type": "cost",
                "title": "Optimize AI Usage Costs",
                "description": "Reduce AI API costs through smart caching and provider selection",
                "impact_level": "medium",
                "estimated_improvement": {"cost_reduction": 35},
                "implementation_effort": "easy",
                "steps": [
                    "Implement response caching",
                    "Use cost-effective providers for simple tasks",
                    "Monitor usage patterns"
                ],
                "confidence_score": 90,
                "potential_risks": ["Cache staleness"]
            }
        ]

        # Apply filters
        if type_filter:
            recommendations = [r for r in recommendations if r["type"] == type_filter]
        if impact_filter:
            recommendations = [r for r in recommendations if r["impact_level"] == impact_filter]

        return {
            "success": True,
            "workflow_id": workflow_id,
            "recommendations": recommendations,
            "total_recommendations": len(recommendations),
            "filters_applied": {
                "type": type_filter,
                "impact": impact_filter
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get recommendations: {str(e)}"
        )

@router.get("/api/v1/workflows/optimization-types")
async def get_optimization_types():
    """Get available optimization types and their descriptions"""
    types = {
        "performance": {
            "name": "Performance Optimization",
            "description": "Reduce execution time and improve throughput",
            "focus_areas": ["Parallel processing", "Caching", "Query optimization", "Batch operations"]
        },
        "cost": {
            "name": "Cost Optimization",
            "description": "Reduce operational costs and resource usage",
            "focus_areas": ["AI usage optimization", "API call reduction", "Resource scheduling"]
        },
        "reliability": {
            "name": "Reliability Optimization",
            "description": "Improve success rate and reduce failures",
            "focus_areas": ["Error handling", "Retry logic", "Redundancy", "Monitoring"]
        },
        "efficiency": {
            "name": "Efficiency Optimization",
            "description": "Streamline processes and reduce manual effort",
            "focus_areas": ["Automation", "Process simplification", "Workflow redesign"]
        },
        "security": {
            "name": "Security Optimization",
            "description": "Enhance security and compliance",
            "focus_areas": ["Data encryption", "Access control", "Audit trails"]
        },
        "scalability": {
            "name": "Scalability Optimization",
            "description": "Improve ability to handle increased load",
            "focus_areas": ["Load balancing", "Resource scaling", "Database optimization"]
        }
    }

    return {
        "success": True,
        "optimization_types": types
    }

@router.post("/api/v1/workflows/batch-analysis")
async def batch_analyze_workflows(
    workflows: List[Dict[str, Any]],
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Analyze multiple workflows for optimization opportunities"""
    try:
        if len(workflows) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 workflows can be analyzed in a single batch"
            )

        batch_results = []
        summary = {
            "total_workflows": len(workflows),
            "total_recommendations": 0,
            "common_issues": {},
            "optimization_priorities": {}
        }

        for workflow in workflows:
            try:
                analysis = await optimizer.analyze_workflow(workflow)

                workflow_result = {
                    "workflow_id": analysis.workflow_id,
                    "workflow_name": analysis.workflow_name,
                    "complexity_score": analysis.complexity_score,
                    "failure_points": len(analysis.failure_points),
                    "bottlenecks": len(analysis.bottlenecks),
                    "optimization_opportunities": len(analysis.optimization_opportunities),
                    "top_priority": analysis.optimization_opportunities[0].type.value if analysis.optimization_opportunities else None
                }

                batch_results.append(workflow_result)

                # Update summary
                summary["total_recommendations"] += len(analysis.optimization_opportunities)

                # Track common issues
                for failure_point in analysis.failure_points:
                    for issue in failure_point["issues"]:
                        summary["common_issues"][issue] = summary["common_issues"].get(issue, 0) + 1

                # Track optimization priorities
                for rec in analysis.optimization_opportunities:
                    opt_type = rec.type.value
                    summary["optimization_priorities"][opt_type] = summary["optimization_priorities"].get(opt_type, 0) + 1

            except Exception as e:
                logger.error(f"Failed to analyze workflow: {e}")
                batch_results.append({
                    "workflow_id": workflow.get("id", "unknown"),
                    "error": str(e)
                })

        # Sort common issues and priorities by frequency
        summary["common_issues"] = dict(
            sorted(summary["common_issues"].items(), key=lambda x: x[1], reverse=True)[:10]
        )
        summary["optimization_priorities"] = dict(
            sorted(summary["optimization_priorities"].items(), key=lambda x: x[1], reverse=True)
        )

        return {
            "success": True,
            "batch_analysis": {
                "summary": summary,
                "workflow_results": batch_results
            },
            "analyzed_at": datetime.now(timezone.utc).isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Batch analysis failed: {str(e)}"
        )

@router.get("/api/v1/workflows/optimization-insights")
async def get_optimization_insights(
    time_range: str = Query("7d", description="Time range: 1d, 7d, 30d"),
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Get aggregate insights about workflow optimizations"""
    try:
        # In a real implementation, this would query historical data
        # For now, we'll return sample insights

        insights = {
            "optimization_trends": {
                "most_common_optimizations": {
                    "performance": 45,
                    "cost": 32,
                    "reliability": 28,
                    "efficiency": 25
                },
                "average_improvements": {
                    "performance": {"execution_time": 35, "success_rate": 15},
                    "cost": {"cost_reduction": 28},
                    "reliability": {"error_reduction": 60}
                },
                "implementation_success_rate": 87
            },
            "roi_analysis": {
                "average_time_savings_hours_per_week": 12.5,
                "average_cost_reduction_percentage": 18.3,
                "implementation_payback_period_weeks": 3.2,
                "total_automated_processes": 156
            },
            "recommendation": {
                "priority_focus": "Performance and reliability optimizations show highest ROI",
                "quick_wins": "Focus on AI cost optimization and parallel processing",
                "strategic_initiatives": "Implement comprehensive error handling and monitoring"
            }
        }

        return {
            "success": True,
            "time_range": time_range,
            "insights": insights,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get optimization insights: {str(e)}"
        )

@router.post("/api/v1/workflows/{workflow_id}/implement-optimization")
async def implement_optimization(
    workflow_id: str,
    optimization_id: str = Body(..., embed=True),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    optimizer: AIWorkflowOptimizer = Depends(get_ai_workflow_optimizer)
):
    """Initiate implementation of a specific optimization"""
    try:
        # Create implementation job
        job_id = f"opt_job_{workflow_id}_{optimization_id}_{int(datetime.now().timestamp())}"

        # Start implementation in background
        background_tasks.add_task(
            self._execute_optimization_implementation,
            job_id,
            workflow_id,
            optimization_id
        )

        return {
            "success": True,
            "job_id": job_id,
            "status": "initiated",
            "message": f"Optimization {optimization_id} implementation started for workflow {workflow_id}",
            "estimated_completion": "5-10 minutes"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate optimization: {str(e)}"
        )

async def _execute_optimization_implementation(
    self,
    job_id: str,
    workflow_id: str,
    optimization_id: str
):
    """Execute optimization implementation in background"""
    # This would contain the actual implementation logic
    # For now, it's a placeholder
    await asyncio.sleep(300)  # Simulate 5 minutes of work
    logger.info(f"Completed optimization implementation job {job_id}")

# Helper functions

def _calculate_risk_level(analysis) -> str:
    """Calculate overall risk level for workflow"""
    total_issues = len(analysis.failure_points) + len(analysis.bottlenecks)
    critical_issues = sum(
        1 for fp in analysis.failure_points
        if fp.get("risk_level") == "high"
    )

    if critical_issues > 0 or total_issues > 5:
        return "high"
    elif total_issues > 2:
        return "medium"
    else:
        return "low"

def _group_recommendations_by_type(recommendations) -> Dict[str, List[Dict]]:
    """Group recommendations by optimization type"""
    grouped = {}
    for rec in recommendations:
        rec_dict = {
            "id": rec.id,
            "title": rec.title,
            "impact_level": rec.impact_level.value,
            "effort": rec.implementation_effort,
            "confidence": rec.confidence_score
        }

        type_name = rec.type.value
        if type_name not in grouped:
            grouped[type_name] = []
        grouped[type_name].append(rec_dict)

    return grouped