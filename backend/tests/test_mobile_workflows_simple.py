"""
Simple Mobile Workflow API Tests

Tests for mobile-optimized workflow endpoints without loading the full app.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, Mock
import pytest

from api.mobile_workflows import _load_workflow_definition, router


class TestMobileWorkflowsSimple:
    """Simple test suite for mobile workflow APIs"""

    def test_load_workflow_definition(self):
        """Test the _load_workflow_definition helper function"""
        db = Mock()

        # Test with non-existent workflow
        result = _load_workflow_definition(db, "nonexistent")
        assert result is None

    def test_router_creation(self):
        """Test that the router is created successfully"""
        assert router is not None
        assert router.prefix == "/api/mobile/workflows"
        assert "mobile-workflows" in router.tags

    def test_module_loads(self):
        """Test that the mobile workflows module loads correctly"""
        import api.mobile_workflows as mw
        assert hasattr(mw, 'router')
        assert hasattr(mw, 'TriggerRequest')
        assert hasattr(mw, 'TriggerResponse')

    def test_trigger_request_model(self):
        """Test TriggerRequest model"""
        from api.mobile_workflows import TriggerRequest

        # Test creating a request with required fields
        request = TriggerRequest(
            workflow_id="test_workflow",
            synchronous=False
        )
        assert request.workflow_id == "test_workflow"
        assert request.synchronous is False
        assert request.parameters == {}

    def test_trigger_request_with_params(self):
        """Test TriggerRequest with parameters"""
        from api.mobile_workflows import TriggerRequest

        request = TriggerRequest(
            workflow_id="test_workflow",
            synchronous=True,
            parameters={"key": "value"}
        )
        assert request.parameters == {"key": "value"}

    def test_trigger_response_model(self):
        """Test TriggerResponse model"""
        from api.mobile_workflows import TriggerResponse

        response = TriggerResponse(
            execution_id="exec_123",
            status="started",
            message="Workflow started",
            workflow_id="test_workflow"
        )
        assert response.execution_id == "exec_123"
        assert response.status == "started"
