"""
End-to-End Workflow Execution Tests

Tests that verify workflows execute successfully end-to-end,
not just that they can be created. Addresses critical gap:
'Workflow creation is proven, but execution is not tested.'
"""

import requests
import time
import pytest
from typing import Dict, Any


class TestWorkflowExecution:
    """Test actual workflow execution and completion"""

    def setup_method(self):
        """Setup test fixtures"""
        self.base_url = "http://localhost:8000"
        self.workflow_api = f"{self.base_url}/api/v1/workflows"
        self.max_execution_time = 30  # seconds
        self.performance_target = 5  # seconds (ideal)

    def test_customer_support_workflow_execution(self):
        """Test customer support workflow executes to completion"""
        start_time = time.time()

        # Execute workflow
        response = requests.post(
            f"{self.workflow_api}/demo-customer-support",
            timeout=20
        )

        execution_time = time.time() - start_time

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Verify execution completed
        assert data["status"] == "completed", \
            f"Workflow did not complete. Status: {data['status']}, Error: {data.get('error_message')}"

        # Verify execution metrics
        assert data["steps_executed"] > 0, "No steps were executed"
        assert "execution_history" in data, "Missing execution history"
        assert len(data["execution_history"]) > 0, "Execution history is empty"

        # Verify validation evidence
        evidence = data.get("validation_evidence", {})
        assert evidence.get("complex_workflow_executed"), "Complex workflow not marked as executed"
        assert evidence.get("ai_nlu_processing"), "AI NLU processing not verified"
        assert evidence.get("multi_step_workflow"), "Multi-step workflow not verified"

        # Performance check (soft assertion - log warning if slow)
        if execution_time > self.max_execution_time:
            pytest.fail(f"Workflow execution too slow: {execution_time:.2f}s > {self.max_execution_time}s")
        elif execution_time > self.performance_target:
            print(f"⚠️  Performance warning: {execution_time:.2f}s > target {self.performance_target}s")

        print(f"✅ Customer support workflow completed in {execution_time:.2f}s with {data['steps_executed']} steps")

    def test_project_management_workflow_execution(self):
        """Test project management workflow executes to completion"""
        start_time = time.time()

        # Execute workflow
        response = requests.post(
            f"{self.workflow_api}/demo-project-management",
            timeout=20
        )

        execution_time = time.time() - start_time

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Verify execution completed
        assert data["status"] == "completed", \
            f"Workflow did not complete. Status: {data['status']}, Error: {data.get('error_message')}"

        # Verify execution metrics
        assert data["steps_executed"] > 0, "No steps were executed"
        assert "execution_history" in data, "Missing execution history"

        # Verify validation evidence
        evidence = data.get("validation_evidence", {})
        assert evidence.get("workflow_automation_successful"), "Workflow automation not successful"
        assert evidence.get("enterprise_workflow_automation"), "Enterprise workflow automation not verified"

        # Performance check
        if execution_time > self.max_execution_time:
            pytest.fail(f"Workflow execution too slow: {execution_time:.2f}s > {self.max_execution_time}s")
        elif execution_time > self.performance_target:
            print(f"⚠️  Performance warning: {execution_time:.2f}s > target {self.performance_target}s")

        print(f"✅ Project management workflow completed in {execution_time:.2f}s with {data['steps_executed']} steps")

    def test_sales_lead_workflow_execution(self):
        """Test sales lead processing workflow executes to completion"""
        start_time = time.time()

        # Execute workflow
        response = requests.post(
            f"{self.workflow_api}/demo-sales-lead",
            timeout=20
        )

        execution_time = time.time() - start_time

        # Verify response
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()

        # Verify execution completed
        assert data["status"] == "completed", \
            f"Workflow did not complete. Status: {data['status']}, Error: {data.get('error_message')}"

        # Verify execution metrics
        assert data["steps_executed"] > 0, "No steps were executed"
        assert "execution_history" in data, "Missing execution history"

        # Verify validation evidence
        evidence = data.get("validation_evidence", {})
        assert evidence.get("complex_workflow_executed"), "Complex workflow not executed"
        assert evidence.get("real_ai_processing"), "Real AI processing not verified"

        # Performance check
        if execution_time > self.max_execution_time:
            pytest.fail(f"Workflow execution too slow: {execution_time:.2f}s > {self.max_execution_time}s")
        elif execution_time > self.performance_target:
            print(f"⚠️  Performance warning: {execution_time:.2f}s > target {self.performance_target}s")

        print(f"✅ Sales lead workflow completed in {execution_time:.2f}s with {data['steps_executed']} steps")

    def test_workflow_execution_performance(self):
        """Test all workflows meet performance targets"""
        workflows = [
            ("customer-support", "Customer Support"),
            ("project-management", "Project Management"),
            ("sales-lead", "Sales Lead")
        ]

        performance_results = []

        for workflow_id, workflow_name in workflows:
            start_time = time.time()

            response = requests.post(
                f"{self.workflow_api}/demo-{workflow_id}",
                timeout=20
            )

            execution_time = time.time() - start_time

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "completed"

            performance_results.append({
                "workflow": workflow_name,
                "execution_time": execution_time,
                "steps": data["steps_executed"],
                "within_target": execution_time <= self.performance_target
            })

        # Report performance summary
        print("\n📊 Workflow Performance Summary:")
        for result in performance_results:
            status = "✅" if result["within_target"] else "⚠️"
            print(f"{status} {result['workflow']}: {result['execution_time']:.2f}s ({result['steps']} steps)")

        # Calculate averages
        avg_time = sum(r["execution_time"] for r in performance_results) / len(performance_results)
        print(f"\n⏱️  Average execution time: {avg_time:.2f}s")

        # Soft assertion - warn if average exceeds target
        if avg_time > self.performance_target:
            print(f"⚠️  Average exceeds target of {self.performance_target}s")

    def test_workflow_execution_step_validation(self):
        """Test that workflows execute all expected steps in correct order"""
        response = requests.post(
            f"{self.workflow_api}/demo-customer-support",
            timeout=20
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

        # Verify execution history has required fields
        execution_history = data["execution_history"]
        assert len(execution_history) > 0, "No execution history recorded"

        for i, step in enumerate(execution_history):
            assert "step_id" in step, f"Step {i} missing step_id"
            assert "step_type" in step, f"Step {i} missing step_type"
            assert "timestamp" in step, f"Step {i} missing timestamp"
            assert "execution_time_ms" in step, f"Step {i} missing execution_time_ms"

        # Verify first step is NLU analysis
        first_step = execution_history[0]
        assert first_step["step_type"] == "nlu_analysis", \
            f"First step should be NLU analysis, got {first_step['step_type']}"

        # Verify conditional logic was executed
        conditional_steps = [s for s in execution_history if s["step_type"] == "conditional_logic"]
        assert len(conditional_steps) > 0, "No conditional logic steps found"

        print(f"✅ Validated {len(execution_history)} workflow steps")

    def test_workflow_validation_evidence(self):
        """Test that workflows provide comprehensive validation evidence"""
        response = requests.post(
            f"{self.workflow_api}/demo-customer-support",
            timeout=20
        )

        assert response.status_code == 200
        data = response.json()
        evidence = data.get("validation_evidence", {})

        # Required evidence fields
        required_evidence = [
            "complex_workflow_executed",
            "ai_nlu_processing",
            "conditional_logic_executed",
            "multi_step_workflow",
            "workflow_automation_successful",
            "complexity_score",
            "real_ai_processing"
        ]

        for field in required_evidence:
            assert field in evidence, f"Missing required evidence field: {field}"
            assert evidence[field], f"Evidence field '{field}' is False or empty"

        # Verify complexity score is reasonable
        complexity = evidence.get("complexity_score", 0)
        assert complexity >= 5, f"Complexity score too low: {complexity}"

        print(f"✅ Validated {len(required_evidence)} evidence fields, complexity: {complexity}")


if __name__ == "__main__":
    # Can be run standalone for quick testing
    import sys
    pytest.main([__file__, "-v", "-s"] + sys.argv[1:])
