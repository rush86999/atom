"""
Multi-Integration Workflow Routes Unit Tests

Tests for multi-integration workflow automation APIs including:
- Enhanced workflow intelligence (analyze, generate)
- Enhanced workflow optimization (analyze, apply)
- Enhanced workflow monitoring (start, health, metrics)
- Enhanced workflow troubleshooting (analyze, resolve)
- WhatsApp workflow automation
- Step testing functionality

Coverage: Multi-integration workflow routes (782 lines)
Tests: 25-30 comprehensive tests
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from integrations.workflow_automation_routes import router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create TestClient for workflow automation routes."""
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


@pytest.fixture
def mock_intelligence():
    """Create mock WorkflowIntelligenceIntegration."""
    mock = MagicMock()
    mock.analyze_workflow_request.return_value = {
        "analysis": {"summary": "Test analysis", "complexity": "medium"},
        "detected_services": ["slack", "asana"],
        "confidence_score": 0.85,
        "recommendations": ["Use webhooks for real-time updates"]
    }
    mock.generate_optimized_workflow.return_value = {
        "workflow": {"steps": [{"action": "send_message"}]},
        "optimization_suggestions": ["Add error handling"],
        "estimated_performance": 0.92
    }
    return mock


@pytest.fixture
def mock_optimization():
    """Create mock WorkflowOptimizationIntegration."""
    mock = MagicMock()
    mock.analyze_workflow_performance.return_value = {
        "analysis": {"summary": "Performance bottlenecks detected", "bottlenecks": ["api_calls"]},
        "performance_metrics": {"execution_time": 5.2, "memory_usage": "150MB"},
        "optimization_opportunities": [{"type": "caching", "impact": "high"}],
        "estimated_improvement": 0.35
    }
    mock.apply_optimizations.return_value = {
        "optimized_workflow": {"steps": [{"action": "send_message", "cached": True}]},
        "applied_optimizations": ["added_caching"],
        "performance_improvement": 0.30
    }
    return mock


@pytest.fixture
def mock_monitoring():
    """Create mock WorkflowMonitoringIntegration."""
    mock = MagicMock()
    mock.start_monitoring.return_value = {
        "monitoring_id": "mon-123",
        "status": "monitoring_started"
    }
    mock.get_workflow_health.return_value = {
        "health_score": 0.92,
        "status": "healthy",
        "issues": [],
        "recommendations": []
    }
    mock.get_workflow_metrics.return_value = {
        "metrics": {"total_executions": 100, "success_rate": 0.95},
        "trends": {"execution_time": "stable"},
        "alerts": []
    }
    return mock


@pytest.fixture
def mock_troubleshooting():
    """Create mock WorkflowTroubleshootingIntegration."""
    mock = MagicMock()
    mock.analyze_workflow_issues.return_value = {
        "issues": [{"type": "timeout", "severity": "high"}],
        "root_causes": ["Network latency"],
        "recommendations": ["Increase timeout"],
        "confidence_score": 0.88
    }
    mock.auto_resolve_issues.return_value = {
        "resolved_issues": ["timeout_config_fixed"],
        "remaining_issues": [],
        "resolution_status": "fully_resolved"
    }
    return mock


# ============================================================================
# GET /workflows/auth/url - Auth URL Tests
# ============================================================================

def test_get_auth_url(client):
    """Test getting workflow auth URL."""
    response = client.get("/workflows/auth/url")

    assert response.status_code == 200
    data = response.json()
    assert "url" in data
    assert "timestamp" in data


# ============================================================================
# GET /workflows/callback - OAuth Callback Tests
# ============================================================================

def test_handle_oauth_callback(client):
    """Test handling OAuth callback."""
    response = client.get("/workflows/callback?code=test_code")

    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert "successful" in data.get("message", "")


# ============================================================================
# POST /workflows/test-step - Step Testing Tests
# ============================================================================

def test_test_workflow_step_success(client):
    """Test testing a workflow step successfully."""
    step_request = {
        "service": "Slack",
        "action": "send_message",
        "parameters": {
            "channel": "#test",
            "message": "Test message"
        },
        "workflow_id": "wf-123",
        "step_id": "step-1"
    }

    response = client.post("/workflows/test-step", json=step_request)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "result" in data
    assert "duration_ms" in data


def test_test_workflow_step_minimal(client):
    """Test testing a step with minimal parameters."""
    step_request = {
        "service": "Asana",
        "action": "create_task"
    }

    response = client.post("/workflows/test-step", json=step_request)

    assert response.status_code == 200
    assert response.json()["success"] is True


def test_test_workflow_step_with_error(client):
    """Test step testing with simulated error."""
    step_request = {
        "service": "InvalidService",
        "action": "invalid_action"
    }

    # Should still return success even for invalid service in test mode
    response = client.post("/workflows/test-step", json=step_request)

    # Response should indicate success even if service doesn't exist
    assert response.status_code == 200


# ============================================================================
# POST /workflows/enhanced/intelligence/analyze - Intelligence Analysis Tests
# ============================================================================

@pytest.mark.parametrize("enhanced_intelligence", [True, False])
def test_enhanced_intelligence_analyze(client, enhanced_intelligence):
    """Test enhanced workflow intelligence analysis."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', enhanced_intelligence):
        request_data = {
            "user_input": "Create a workflow that sends a Slack message when an Asana task is completed",
            "context": {"project": "Project X"},
            "enhanced_intelligence": True
        }

        if not enhanced_intelligence:
            response = client.post("/workflows/enhanced/intelligence/analyze", json=request_data)
            assert response.status_code == 503
        else:
            with patch('integrations.workflow_automation_routes.intelligence') as mock_int:
                mock_int.analyze_workflow_request.return_value = {
                    "analysis": {"summary": "Workflow analysis complete"},
                    "detected_services": ["slack", "asana"],
                    "confidence_score": 0.92,
                    "recommendations": ["Use webhooks"]
                }

                response = client.post("/workflows/enhanced/intelligence/analyze", json=request_data)

                assert response.status_code == 200
                data = response.json()
                assert data["success"] is True
                assert "analysis" in data
                assert "detected_services" in data


def test_enhanced_intelligence_analyze_with_context(client):
    """Test intelligence analysis with rich context."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.intelligence') as mock_int:
        mock_int.analyze_workflow_request.return_value = {
            "analysis": {"summary": "Enhanced analysis"},
            "detected_services": ["jira", "github"],
            "confidence_score": 0.95,
            "recommendations": ["Use GitHub webhooks", "Jira integration"]
        }

        request_data = {
            "user_input": "Integrate GitHub and Jira",
            "context": {
                "repositories": ["repo1", "repo2"],
                "projects": ["PROJ-1", "PROJ-2"]
            }
        }

        response = client.post("/workflows/enhanced/intelligence/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["detected_services"] == ["jira", "github"]


def test_enhanced_intelligence_analyze_error(client):
    """Test intelligence analysis error handling."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.intelligence') as mock_int:
        mock_int.analyze_workflow_request.side_effect = Exception("Analysis failed")

        request_data = {
            "user_input": "Test input",
            "enhanced_intelligence": True
        }

        response = client.post("/workflows/enhanced/intelligence/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "error" in data


# ============================================================================
# POST /workflows/enhanced/intelligence/generate - Workflow Generation Tests
# ============================================================================

def test_enhanced_intelligence_generate(client):
    """Test enhanced workflow generation."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.intelligence') as mock_int:
        mock_int.generate_optimized_workflow.return_value = {
            "workflow": {
                "id": "wf-generated",
                "steps": [
                    {"action": "trigger", "type": "webhook"},
                    {"action": "send_message", "service": "slack"}
                ]
            },
            "optimization_suggestions": ["Add error handling", "Use async execution"],
            "estimated_performance": 0.94
        }

        request_data = {
            "user_input": "Create a Slack notification workflow",
            "optimization_strategy": "performance",
            "enhanced_intelligence": True
        }

        response = client.post("/workflows/enhanced/intelligence/generate", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "workflow" in data
        assert "optimization_suggestions" in data
        assert data["estimated_performance"] == 0.94


def test_enhanced_intelligence_generate_with_strategies(client):
    """Test workflow generation with different optimization strategies."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.intelligence') as mock_int:
        mock_int.generate_optimized_workflow.return_value = {
            "workflow": {"steps": []},
            "optimization_suggestions": [],
            "estimated_performance": 0.88
        }

        strategies = ["performance", "cost", "reliability"]
        for strategy in strategies:
            request_data = {
                "user_input": "Test workflow",
                "optimization_strategy": strategy
            }

            response = client.post("/workflows/enhanced/intelligence/generate", json=request_data)

            assert response.status_code == 200
            assert response.json()["success"] is True


# ============================================================================
# POST /workflows/enhanced/optimization/analyze - Optimization Analysis Tests
# ============================================================================

def test_enhanced_optimization_analyze(client):
    """Test enhanced workflow optimization analysis."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.optimization') as mock_opt:
        mock_opt.analyze_workflow_performance.return_value = {
            "analysis": {"summary": "Performance analysis complete"},
            "performance_metrics": {
                "avg_execution_time": 3.5,
                "p95_execution_time": 7.2,
                "success_rate": 0.97
            },
            "optimization_opportunities": [
                {"type": "caching", "impact": "high", "estimated_saving": "40%"},
                {"type": "parallelization", "impact": "medium", "estimated_saving": "25%"}
            ],
            "estimated_improvement": 0.45
        }

        request_data = {
            "workflow": {"steps": [{"action": "api_call"}]},
            "strategy": "performance"
        }

        response = client.post("/workflows/enhanced/optimization/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analysis" in data
        assert "performance_metrics" in data
        assert len(data["optimization_opportunities"]) == 2


def test_enhanced_optimization_analyze_cost_strategy(client):
    """Test optimization analysis with cost strategy."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.optimization') as mock_opt:
        mock_opt.analyze_workflow_performance.return_value = {
            "analysis": {"summary": "Cost optimization opportunities"},
            "performance_metrics": {"monthly_cost": 150.00},
            "optimization_opportunities": [
                {"type": "reduce_api_calls", "impact": "high"}
            ],
            "estimated_improvement": 0.30
        }

        request_data = {
            "workflow": {"steps": []},
            "strategy": "cost"
        }

        response = client.post("/workflows/enhanced/optimization/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["analysis"]["summary"] == "Cost optimization opportunities"


# ============================================================================
# POST /workflows/enhanced/optimization/apply - Apply Optimizations Tests
# ============================================================================

def test_enhanced_optimization_apply(client):
    """Test applying workflow optimizations."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.optimization') as mock_opt:
        mock_opt.apply_optimizations.return_value = {
            "optimized_workflow": {
                "steps": [
                    {"action": "api_call", "cached": True, "timeout": 30}
                ]
            },
            "applied_optimizations": [
                "added_response_caching",
                "optimized_timeout_settings",
                "enabled_compression"
            ],
            "performance_improvement": 0.42
        }

        request_data = {
            "workflow": {"steps": [{"action": "api_call"}]},
            "optimizations": [
                {"type": "caching", "config": {"ttl": 300}},
                {"type": "timeout", "config": {"duration": 30}}
            ]
        }

        response = client.post("/workflows/enhanced/optimization/apply", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "optimized_workflow" in data
        assert len(data["applied_optimizations"]) == 3
        assert data["performance_improvement"] == 0.42


def test_enhanced_optimization_apply_multiple(client):
    """Test applying multiple optimizations at once."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.optimization') as mock_opt:
        mock_opt.apply_optimizations.return_value = {
            "optimized_workflow": {"steps": []},
            "applied_optimizations": ["opt1", "opt2", "opt3", "opt4"],
            "performance_improvement": 0.55
        }

        request_data = {
            "workflow": {"steps": []},
            "optimizations": [
                {"type": "opt1"},
                {"type": "opt2"},
                {"type": "opt3"},
                {"type": "opt4"}
            ]
        }

        response = client.post("/workflows/enhanced/optimization/apply", json=request_data)

        assert response.status_code == 200
        assert len(response.json()["applied_optimizations"]) == 4


# ============================================================================
# POST /workflows/enhanced/monitoring/start - Monitoring Start Tests
# ============================================================================

def test_enhanced_monitoring_start(client):
    """Test starting enhanced workflow monitoring."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.monitoring') as mock_mon:
        mock_mon.start_monitoring.return_value = {
            "monitoring_id": "mon-abc123",
            "status": "monitoring_active",
            "features": ["real_time", "alerts", "anomaly_detection"]
        }

        request_data = {
            "workflow_id": "wf-123"
        }

        response = client.post("/workflows/enhanced/monitoring/start", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["monitoring_id"] == "mon-abc123"
        assert data["status"] == "monitoring_active"


# ============================================================================
# GET /workflows/enhanced/monitoring/health - Monitoring Health Tests
# ============================================================================

def test_enhanced_monitoring_health(client):
    """Test getting workflow health status."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.monitoring') as mock_mon:
        mock_mon.get_workflow_health.return_value = {
            "health_score": 0.88,
            "status": "healthy",
            "issues": [],
            "recommendations": ["Consider adding retry logic"]
        }

        response = client.get("/workflows/enhanced/monitoring/health?workflow_id=wf-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["health_score"] == 0.88
        assert data["status"] == "healthy"


def test_enhanced_monitoring_health_with_issues(client):
    """Test health check with detected issues."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.monitoring') as mock_mon:
        mock_mon.get_workflow_health.return_value = {
            "health_score": 0.62,
            "status": "degraded",
            "issues": [
                {"type": "slow_response", "severity": "medium"},
                {"type": "high_error_rate", "severity": "high"}
            ],
            "recommendations": [
                "Increase timeout",
                "Add retry mechanism",
                "Scale up resources"
            ]
        }

        response = client.get("/workflows/enhanced/monitoring/health?workflow_id=wf-456")

        assert response.status_code == 200
        data = response.json()
        assert data["health_score"] == 0.62
        assert data["status"] == "degraded"
        assert len(data["issues"]) == 2


# ============================================================================
# GET /workflows/enhanced/monitoring/metrics - Monitoring Metrics Tests
# ============================================================================

def test_enhanced_monitoring_metrics(client):
    """Test getting workflow monitoring metrics."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.monitoring') as mock_mon:
        mock_mon.get_workflow_metrics.return_value = {
            "metrics": {
                "total_executions": 542,
                "successful_executions": 519,
                "failed_executions": 23,
                "avg_execution_time": 2.8,
                "success_rate": 0.958
            },
            "trends": {
                "execution_time": "decreasing",
                "error_rate": "stable",
                "throughput": "increasing"
            },
            "alerts": []
        }

        response = client.get("/workflows/enhanced/monitoring/metrics?workflow_id=wf-123&metric_type=all")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "metrics" in data
        assert "trends" in data
        assert data["metrics"]["total_executions"] == 542


def test_enhanced_monitoring_metrics_with_alerts(client):
    """Test metrics with active alerts."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.monitoring') as mock_mon:
        mock_mon.get_workflow_metrics.return_value = {
            "metrics": {"total_executions": 100},
            "trends": {},
            "alerts": [
                {"type": "high_error_rate", "severity": "warning", "threshold": 0.05, "current": 0.08},
                {"type": "slow_execution", "severity": "info", "threshold": 5.0, "current": 5.8}
            ]
        }

        response = client.get("/workflows/enhanced/monitoring/metrics?workflow_id=wf-789&metric_type=performance")

        assert response.status_code == 200
        data = response.json()
        assert len(data["alerts"]) == 2


# ============================================================================
# POST /workflows/enhanced/troubleshooting/analyze - Troubleshooting Analysis Tests
# ============================================================================

def test_enhanced_troubleshooting_analyze(client):
    """Test workflow troubleshooting analysis."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.troubleshooting') as mock_troub:
        mock_troub.analyze_workflow_issues.return_value = {
            "issues": [
                {"type": "authentication_error", "severity": "critical", "location": "step_3"},
                {"type": "rate_limit", "severity": "high", "location": "step_5"}
            ],
            "root_causes": [
                "Invalid API credentials",
                "Exceeding API rate limits",
                "Missing exponential backoff"
            ],
            "recommendations": [
                "Update API credentials",
                "Implement rate limiting",
                "Add retry with backoff"
            ],
            "confidence_score": 0.91
        }

        request_data = {
            "workflow_id": "wf-123",
            "error_logs": [
                "Authentication failed for service X",
                "Rate limit exceeded at step 5"
            ]
        }

        response = client.post("/workflows/enhanced/troubleshooting/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["issues"]) == 2
        assert len(data["root_causes"]) == 3
        assert data["confidence_score"] == 0.91


# ============================================================================
# POST /workflows/enhanced/troubleshooting/resolve - Auto-Resolution Tests
# ============================================================================

def test_enhanced_troubleshooting_resolve(client):
    """Test automatic issue resolution."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.troubleshooting') as mock_troub:
        mock_troub.auto_resolve_issues.return_value = {
            "resolved_issues": [
                "fixed_authentication_config",
                "added_rate_limiting",
                "implemented_retry_logic"
            ],
            "remaining_issues": [],
            "resolution_status": "fully_resolved"
        }

        request_data = {
            "workflow_id": "wf-123",
            "issues": [
                {"type": "auth_error", "resolution": "update_creds"},
                {"type": "rate_limit", "resolution": "add_backoff"}
            ]
        }

        response = client.post("/workflows/enhanced/troubleshooting/resolve", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["resolved_issues"]) == 3
        assert data["resolution_status"] == "fully_resolved"


def test_enhanced_troubleshooting_resolve_partial(client):
    """Test partial automatic resolution."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.troubleshooting') as mock_troub:
        mock_troub.auto_resolve_issues.return_value = {
            "resolved_issues": ["fixed_simple_config"],
            "remaining_issues": [
                {"type": "complex_issue", "requires_manual": True}
            ],
            "resolution_status": "partial"
        }

        request_data = {
            "workflow_id": "wf-456",
            "issues": [
                {"type": "simple"},
                {"type": "complex"}
            ]
        }

        response = client.post("/workflows/enhanced/troubleshooting/resolve", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["resolution_status"] == "partial"
        assert len(data["remaining_issues"]) == 1


# ============================================================================
# GET /workflows/enhanced/status - Enhanced Status Tests
# ============================================================================

def test_enhanced_workflow_status_available(client):
    """Test enhanced workflow status when available."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', True), \
         patch('integrations.workflow_automation_routes.intelligence', MagicMock()), \
         patch('integrations.workflow_automation_routes.optimization', MagicMock()), \
         patch('integrations.workflow_automation_routes.monitoring', MagicMock()), \
         patch('integrations.workflow_automation_routes.troubleshooting', MagicMock()):

        response = client.get("/workflows/enhanced/status")

        assert response.status_code == 200
        data = response.json()
        assert data["enhanced_workflow_available"] is True
        assert "components" in data
        assert "endpoints" in data
        assert data["components"]["intelligence"] is True
        assert data["components"]["optimization"] is True


def test_enhanced_workflow_status_unavailable(client):
    """Test enhanced workflow status when unavailable."""
    with patch('integrations.workflow_automation_routes.ENHANCED_WORKFLOW_AVAILABLE', False):

        response = client.get("/workflows/enhanced/status")

        assert response.status_code == 200
        data = response.json()
        assert data["enhanced_workflow_available"] is False


# ============================================================================
# POST /workflows/whatsapp/automate - WhatsApp Automation Tests
# ============================================================================

def test_whatsapp_customer_support_automation(client):
    """Test WhatsApp customer support automation."""
    request_data = {
        "type": "customer_support",
        "parameters": {
            "trigger_keywords": ["help", "support"],
            "auto_response": "Thank you for contacting support!",
            "escalate_conditions": ["urgent"]
        }
    }

    response = client.post("/workflows/whatsapp/automate", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["workflow_type"] == "customer_support"
    assert "result" in data


def test_whatsapp_appointment_reminder_automation(client):
    """Test WhatsApp appointment reminder automation."""
    request_data = {
        "type": "appointment_reminder",
        "parameters": {
            "reminder_intervals": [24, 2, 0.5],
            "template_name": "appointment_reminder"
        }
    }

    response = client.post("/workflows/whatsapp/automate", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["workflow_type"] == "appointment_reminder"


def test_whatsapp_marketing_campaign_automation(client):
    """Test WhatsApp marketing campaign automation."""
    request_data = {
        "type": "marketing_campaign",
        "parameters": {
            "campaign_type": "promotion",
            "target_audience": "vip_customers",
            "message_template": "special_offer"
        }
    }

    response = client.post("/workflows/whatsapp/automate", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["result"]["campaign_type"] == "promotion"


def test_whatsapp_follow_up_automation(client):
    """Test WhatsApp follow-up sequence automation."""
    request_data = {
        "type": "follow_up_sequence",
        "parameters": {
            "follow_up_delays": [1, 3, 7],
            "follow_up_templates": ["follow_1", "follow_2", "follow_3"]
        }
    }

    response = client.post("/workflows/whatsapp/automate", json=request_data)

    assert response.status_code == 200
    data = response.json()
    assert data["workflow_type"] == "follow_up_sequence"


def test_whatsapp_automation_invalid_type(client):
    """Test WhatsApp automation with invalid type."""
    request_data = {
        "type": "invalid_type",
        "parameters": {}
    }

    response = client.post("/workflows/whatsapp/automate", json=request_data)

    # Should return error for invalid type
    assert response.status_code == 200
    data = response.json()
    # The endpoint catches the error and returns success=False
    assert data.get("success") is False or "error" in data


def test_whatsapp_automation_unavailable_integration(client):
    """Test WhatsApp automation when integration unavailable."""
    # This test verifies the graceful degradation when WhatsApp integration is missing
    with patch('integrations.workflow_automation_routes._handle_customer_support_automation') as mock_handler:
        mock_handler.side_effect = ImportError("WhatsApp integration not found")

        request_data = {
            "type": "customer_support",
            "parameters": {}
        }

        response = client.post("/workflows/whatsapp/automate", json=request_data)

        # Should handle the error gracefully
        assert response.status_code == 200
