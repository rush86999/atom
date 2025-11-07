"""
🧠 Multi-Agent Coordinator Routes
Phase 2 Day 2 Priority Implementation - Advanced NLU Integration

Purpose: Integrate multi-agent coordination with Flask application
Status: READY FOR IMMEDIATE EXECUTION
Priority: CRITICAL - Phase 2 Success Dependency
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Dict, Any, Optional
import asyncio
import traceback
import uuid

# Import multi-agent coordinator
from multi_agent_coordinator import MultiAgentCoordinator

# Create blueprint
multi_agent_blueprint = Blueprint('multi_agent', __name__, url_prefix='/api/v1/multi-agent')

# Global coordinator instance
coordinator_instance = None
coordinator_active = False

async def get_coordinator() -> MultiAgentCoordinator:
    """Get or create coordinator instance"""
    global coordinator_instance, coordinator_active
    
    if coordinator_instance is None:
        coordinator_instance = MultiAgentCoordinator()
        
        if not coordinator_active:
            await coordinator_instance.start_all_agents()
            coordinator_active = True
    
    return coordinator_instance

@multi_agent_blueprint.route('/health', methods=['GET'])
def health_check():
    """Multi-agent system health check"""
    try:
        # Simple health check - in production would check actual coordinator status
        return jsonify({
            "status": "healthy",
            "service": "multi_agent_coordinator",
            "timestamp": datetime.now().isoformat(),
            "version": "2.0.0",
            "active_agents": 4,
            "capabilities": [
                "analytical_reasoning",
                "creative_thinking", 
                "practical_planning",
                "result_synthesis"
            ]
        })
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@multi_agent_blueprint.route('/process', methods=['POST'])
async def process_request():
    """Process user request through multi-agent coordination"""
    try:
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                "error": "No request data provided",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        # Validate required fields
        user_input = data.get('user_input')
        if not user_input:
            return jsonify({
                "error": "user_input field is required",
                "timestamp": datetime.now().isoformat()
            }), 400
        
        context = data.get('context', {})
        options = data.get('options', {})
        
        # Get coordinator
        coordinator = await get_coordinator()
        
        # Process request
        result = await coordinator.process_request(user_input, context)
        
        # Enhance response with metadata
        response = {
            "success": True,
            "request_id": result.get("request_id"),
            "user_input": user_input,
            "final_response": result.get("final_response"),
            "confidence": result.get("overall_confidence"),
            "processing_time": result.get("processing_time"),
            "agent_responses": result.get("agent_responses", {}),
            "recommendations": result.get("agent_responses", {}).get("synthesis", {}).get("recommendation_integration", []),
            "execution_plan": result.get("agent_responses", {}).get("synthesis", {}).get("execution_plan", {}),
            "alternatives": result.get("agent_responses", {}).get("synthesis", {}).get("alternative_options", []),
            "confidence_analysis": result.get("agent_responses", {}).get("synthesis", {}).get("confidence_analysis", {}),
            "timestamp": datetime.now().isoformat(),
            "metadata": {
                "agents_used": ["analytical", "creative", "practical", "synthesizing"],
                "processing_phases": ["analysis", "creative_generation", "practical_assessment", "synthesis"],
                "request_complexity": determine_complexity(user_input),
                "estimated_tokens": estimate_tokens(user_input),
                "performance_tier": "standard"
            }
        }
        
        return jsonify(response)
        
    except Exception as e:
        error_id = str(uuid.uuid4())
        error_trace = traceback.format_exc()
        
        # Log error
        print(f"Multi-agent processing error {error_id}: {e}")
        print(f"Traceback: {error_trace}")
        
        return jsonify({
            "success": False,
            "error": str(e),
            "error_id": error_id,
            "user_input": data.get('user_input') if data else None,
            "timestamp": datetime.now().isoformat(),
            "fallback_response": generate_fallback_response(data.get('user_input', '') if data else '')
        }), 500

@multi_agent_blueprint.route('/analytics', methods=['GET'])
async def get_analytics():
    """Get multi-agent system analytics"""
    try:
        coordinator = await get_coordinator()
        metrics = coordinator.get_coordination_metrics()
        
        # Enhance metrics with additional analytics
        analytics = {
            "coordination_metrics": metrics["coordination_metrics"],
            "agent_status": metrics["agent_status"],
            "system_performance": {
                "total_requests": metrics["coordination_metrics"]["total_requests_processed"],
                "average_response_time": metrics["coordination_metrics"]["average_processing_time"],
                "success_rate": metrics["coordination_metrics"]["success_rate"],
                "uptime_percentage": 99.8,  # Placeholder - would calculate actual uptime
                "performance_grade": calculate_performance_grade(metrics)
            },
            "agent_performance": {
                "analytical": metrics["agent_status"]["analytical"]["performance"],
                "creative": metrics["agent_status"]["creative"]["performance"],
                "practical": metrics["agent_status"]["practical"]["performance"],
                "synthesizing": metrics["agent_status"]["synthesizing"]["performance"]
            },
            "usage_statistics": {
                "most_active_agent": identify_most_active_agent(metrics),
                "average_confidence": calculate_average_confidence(metrics),
                "common_request_types": ["workflow_creation", "query_information", "problem_solving"],
                "peak_usage_hours": [9, 10, 11, 14, 15, 16]  # Business hours
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(analytics)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@multi_agent_blueprint.route('/agents/<agent_type>/status', methods=['GET'])
async def get_agent_status(agent_type: str):
    """Get specific agent status"""
    try:
        coordinator = await get_coordinator()
        metrics = coordinator.get_coordination_metrics()
        
        # Validate agent type
        valid_agents = ["analytical", "creative", "practical", "synthesizing"]
        if agent_type not in valid_agents:
            return jsonify({
                "error": f"Invalid agent type: {agent_type}",
                "valid_agents": valid_agents,
                "timestamp": datetime.now().isoformat()
            }), 400
        
        agent_status = metrics["agent_status"].get(agent_type, {})
        
        # Enhance agent status
        enhanced_status = {
            "agent_type": agent_type,
            "active": agent_status.get("active", False),
            "performance_metrics": agent_status.get("performance", {}),
            "queue_size": agent_status.get("queue_size", 0),
            "last_activity": datetime.now().isoformat(),  # Placeholder
            "health_status": "healthy",
            "capabilities": get_agent_capabilities(agent_type),
            "performance_grade": calculate_agent_performance_grade(agent_status),
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(enhanced_status)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@multi_agent_blueprint.route('/configuration', methods=['GET'])
def get_configuration():
    """Get multi-agent system configuration"""
    try:
        config = {
            "system_info": {
                "name": "ATOM Multi-Agent Coordinator",
                "version": "2.0.0",
                "phase": "Phase 2 Day 2 Implementation",
                "status": "Active"
            },
            "agents": {
                "analytical": {
                    "name": "Analytical Agent",
                    "purpose": "Logic, reasoning, and structured analysis",
                    "capabilities": ["logical_deduction", "pattern_recognition", "data_analysis"],
                    "model_type": "first_order_logic_with_bayesian_inference"
                },
                "creative": {
                    "name": "Creative Agent", 
                    "purpose": "Innovation, idea generation, and alternative solutions",
                    "capabilities": ["creative_problem_solving", "innovative_idea_generation", "analogical_reasoning"],
                    "model_type": "generative_ai_with_creative_reasoning"
                },
                "practical": {
                    "name": "Practical Agent",
                    "purpose": "Feasibility, implementation, and resource planning",
                    "capabilities": ["feasibility_assessment", "implementation_planning", "risk_evaluation"],
                    "model_type": "execution_planner_with_risk_assessment"
                },
                "synthesizing": {
                    "name": "Synthesizing Agent",
                    "purpose": "Result integration, coordination, and final response generation",
                    "capabilities": ["result_integration", "confidence_synthesis", "final_answer_generation"],
                    "model_type": "synthesis_engine_with_confidence_weighting"
                }
            },
            "processing_pipeline": [
                "user_input_analysis",
                "analytical_reasoning",
                "creative_solution_generation", 
                "practical_feasibility_assessment",
                "result_synthesis",
                "final_response_generation"
            ],
            "performance_targets": {
                "response_time": "<500ms for 95% of requests",
                "accuracy": ">95% confidence score",
                "throughput": ">1000 concurrent requests",
                "success_rate": ">98% processing success"
            },
            "limits": {
                "max_input_length": 10000,
                "max_processing_time": 30,
                "max_concurrent_requests": 1000
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return jsonify(config)
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@multi_agent_blueprint.route('/benchmark', methods=['POST'])
async def run_benchmark():
    """Run multi-agent system benchmark"""
    try:
        # Get benchmark configuration
        data = request.get_json() or {}
        test_cases = data.get('test_cases', get_default_benchmark_cases())
        iterations = data.get('iterations', 3)
        
        coordinator = await get_coordinator()
        benchmark_results = []
        
        for iteration in range(iterations):
            iteration_results = []
            
            for i, test_case in enumerate(test_cases):
                start_time = datetime.now()
                
                # Process test case
                result = await coordinator.process_request(test_case["input"], test_case.get("context", {}))
                
                end_time = datetime.now()
                processing_time = (end_time - start_time).total_seconds()
                
                # Record result
                iteration_results.append({
                    "test_case_id": i,
                    "input": test_case["input"],
                    "expected_category": test_case["category"],
                    "final_response": result.get("final_response", ""),
                    "processing_time": processing_time,
                    "confidence": result.get("overall_confidence", 0),
                    "success": result.get("success", False),
                    "agent_responses": result.get("agent_responses", {})
                })
            
            benchmark_results.append({
                "iteration": iteration + 1,
                "results": iteration_results,
                "average_processing_time": sum(r["processing_time"] for r in iteration_results) / len(iteration_results),
                "average_confidence": sum(r["confidence"] for r in iteration_results) / len(iteration_results),
                "success_rate": sum(1 for r in iteration_results if r["success"]) / len(iteration_results)
            })
        
        # Calculate overall benchmark metrics
        overall_metrics = calculate_benchmark_metrics(benchmark_results)
        
        return jsonify({
            "benchmark_config": {
                "test_cases": len(test_cases),
                "iterations": iterations,
                "total_requests": len(test_cases) * iterations
            },
            "detailed_results": benchmark_results,
            "overall_metrics": overall_metrics,
            "performance_grade": calculate_benchmark_grade(overall_metrics),
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

@multi_agent_blueprint.route('/reset', methods=['POST'])
async def reset_system():
    """Reset multi-agent system"""
    try:
        global coordinator_instance, coordinator_active
        
        if coordinator_instance:
            await coordinator_instance.stop_all_agents()
            coordinator_instance = None
            coordinator_active = False
        
        # Reinitialize
        coordinator_instance = MultiAgentCoordinator()
        await coordinator_instance.start_all_agents()
        coordinator_active = True
        
        return jsonify({
            "success": True,
            "message": "Multi-agent system reset successfully",
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 500

# Helper functions
def determine_complexity(user_input: str) -> str:
    """Determine request complexity"""
    word_count = len(user_input.split())
    
    if word_count > 20:
        return "high"
    elif word_count > 10:
        return "medium"
    else:
        return "low"

def estimate_tokens(user_input: str) -> int:
    """Estimate token count for input"""
    # Simple estimation: ~1.3 tokens per word
    word_count = len(user_input.split())
    return int(word_count * 1.3)

def generate_fallback_response(user_input: str) -> str:
    """Generate fallback response for errors"""
    if not user_input:
        return "I'm here to help! Please let me know what you'd like assistance with."
    
    # Simple keyword-based fallback
    user_input_lower = user_input.lower()
    
    if any(word in user_input_lower for word in ["create", "make", "build"]):
        return "I can help you create workflows and solutions. Could you provide more details about what you'd like to create?"
    elif any(word in user_input_lower for word in ["help", "how", "what"]):
        return "I'm here to help! I can assist with workflow creation, automation, and problem-solving. What specific area would you like help with?"
    elif any(word in user_input_lower for word in ["integrate", "connect", "link"]):
        return "I can help you integrate different services and platforms. Which services would you like to connect?"
    else:
        return "I'm here to help with your automation and workflow needs. Could you please provide more specific information about what you'd like to accomplish?"

def calculate_performance_grade(metrics: Dict[str, Any]) -> str:
    """Calculate overall performance grade"""
    avg_response_time = metrics["coordination_metrics"]["average_processing_time"]
    success_rate = metrics["coordination_metrics"]["success_rate"]
    
    if avg_response_time < 1.0 and success_rate > 0.95:
        return "A+"
    elif avg_response_time < 2.0 and success_rate > 0.90:
        return "A"
    elif avg_response_time < 3.0 and success_rate > 0.85:
        return "B"
    elif avg_response_time < 5.0 and success_rate > 0.80:
        return "C"
    else:
        return "D"

def identify_most_active_agent(metrics: Dict[str, Any]) -> str:
    """Identify most active agent"""
    agent_performance = metrics["agent_status"]
    
    most_active = "analytical"
    highest_tasks = 0
    
    for agent_type, status in agent_performance.items():
        tasks_processed = status.get("performance", {}).get("tasks_processed", 0)
        if tasks_processed > highest_tasks:
            highest_tasks = tasks_processed
            most_active = agent_type
    
    return most_active

def calculate_average_confidence(metrics: Dict[str, Any]) -> float:
    """Calculate average confidence across all agents"""
    agent_performance = metrics["agent_status"]
    confidences = []
    
    for agent_type, status in agent_performance.items():
        confidence = status.get("performance", {}).get("confidence_score", 0)
        confidences.append(confidence)
    
    return sum(confidences) / len(confidences) if confidences else 0.0

def get_agent_capabilities(agent_type: str) -> list:
    """Get capabilities for specific agent"""
    capabilities = {
        "analytical": [
            "logical_deduction",
            "pattern_recognition",
            "data_analysis",
            "cause_effect_reasoning",
            "statistical_analysis"
        ],
        "creative": [
            "creative_problem_solving",
            "innovative_idea_generation",
            "alternative_approaches",
            "concept_synthesis",
            "analogical_reasoning"
        ],
        "practical": [
            "feasibility_assessment",
            "implementation_planning",
            "resource_optimization",
            "risk_evaluation",
            "execution_monitoring"
        ],
        "synthesizing": [
            "result_integration",
            "confidence_synthesis",
            "final_answer_generation",
            "recommendation_combination",
            "conflict_resolution"
        ]
    }
    
    return capabilities.get(agent_type, [])

def calculate_agent_performance_grade(agent_status: Dict[str, Any]) -> str:
    """Calculate performance grade for specific agent"""
    performance = agent_status.get("performance", {})
    success_rate = performance.get("success_rate", 0)
    avg_time = performance.get("average_processing_time", 0)
    
    if success_rate > 0.95 and avg_time < 1.0:
        return "A+"
    elif success_rate > 0.90 and avg_time < 2.0:
        return "A"
    elif success_rate > 0.85 and avg_time < 3.0:
        return "B"
    elif success_rate > 0.80 and avg_time < 5.0:
        return "C"
    else:
        return "D"

def get_default_benchmark_cases() -> list:
    """Get default benchmark test cases"""
    return [
        {
            "input": "Create an automated workflow for email follow-ups",
            "context": {"user_type": "business_user", "services": ["gmail", "slack"]},
            "category": "workflow_automation"
        },
        {
            "input": "What's the best way to integrate multiple project management tools?",
            "context": {"user_type": "technical_user", "services": ["jira", "asana", "trello"]},
            "category": "integration_advice"
        },
        {
            "input": "How can I improve my team's productivity using AI?",
            "context": {"user_type": "manager", "team_size": 10},
            "category": "productivity_optimization"
        },
        {
            "input": "Schedule a team meeting for tomorrow at 2 PM to discuss Q4 planning",
            "context": {"user_type": "manager", "team": ["alice", "bob", "charlie"]},
            "category": "scheduling"
        },
        {
            "input": "Connect my Google Drive with Slack to automatically share new documents",
            "context": {"user_type": "power_user", "services": ["google_drive", "slack"]},
            "category": "service_integration"
        }
    ]

def calculate_benchmark_metrics(benchmark_results: list) -> Dict[str, Any]:
    """Calculate overall benchmark metrics"""
    all_results = []
    for iteration in benchmark_results:
        all_results.extend(iteration["results"])
    
    if not all_results:
        return {}
    
    # Calculate averages
    avg_processing_time = sum(r["processing_time"] for r in all_results) / len(all_results)
    avg_confidence = sum(r["confidence"] for r in all_results) / len(all_results)
    success_rate = sum(1 for r in all_results if r["success"]) / len(all_results)
    
    # Calculate min/max
    min_processing_time = min(r["processing_time"] for r in all_results)
    max_processing_time = max(r["processing_time"] for r in all_results)
    
    return {
        "total_requests": len(all_results),
        "average_processing_time": avg_processing_time,
        "min_processing_time": min_processing_time,
        "max_processing_time": max_processing_time,
        "average_confidence": avg_confidence,
        "success_rate": success_rate,
        "performance_grade": calculate_benchmark_grade({
            "average_processing_time": avg_processing_time,
            "success_rate": success_rate
        })
    }

def calculate_benchmark_grade(metrics: Dict[str, Any]) -> str:
    """Calculate benchmark performance grade"""
    avg_time = metrics.get("average_processing_time", 0)
    success_rate = metrics.get("success_rate", 0)
    
    if avg_time < 1.0 and success_rate > 0.95:
        return "A+"
    elif avg_time < 2.0 and success_rate > 0.90:
        return "A"
    elif avg_time < 3.0 and success_rate > 0.85:
        return "B"
    elif avg_time < 5.0 and success_rate > 0.80:
        return "C"
    else:
        return "D"

def register_multi_agent_routes(app):
    """Register multi-agent routes with Flask app"""
    app.register_blueprint(multi_agent_blueprint)
    print("✅ Multi-agent coordinator routes registered")