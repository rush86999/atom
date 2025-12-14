#!/usr/bin/env python3
"""
Simple workflow functionality test
Tests the multi-input, multi-step, multi-output workflow system without UI dependencies
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_workflow_parameter_validator():
    """Test the workflow parameter validator"""
    print("\nTESTING: Workflow Parameter Validator")

    try:
        from backend.core.workflow_parameter_validator import (
            WorkflowParameterValidator,
            create_email_validation_rules,
            create_number_validation_rules
        )

        validator = WorkflowParameterValidator()

        # Test email validation
        email_rules = create_email_validation_rules()
        parameters = {
            "email": {
                "name": "email",
                "type": "string",
                "label": "Email Address",
                "validation_rules": email_rules
            }
        }

        # Test valid email
        inputs = {"email": "test@example.com"}
        result = validator.validate_parameters(parameters, inputs)

        assert result["valid"], "Valid email should pass validation"
        print("  PASS Email validation working")

        # Test invalid email
        inputs = {"email": "invalid-email"}
        result = validator.validate_parameters(parameters, inputs)

        assert not result["valid"], "Invalid email should fail validation"
        assert "email" in result["errors"], "Email error should be in errors"
        print("  PASS Invalid email rejection working")

        # Test conditional validation
        validator.register_field_validator("password", "required", {"required": True})

        conditional_parameters = {
            "user_type": {
                "name": "user_type",
                "type": "string",
                "label": "User Type"
            },
            "password": {
                "name": "password",
                "type": "string",
                "label": "Password",
                "show_when": {"user_type": "admin"}
            }
        }

        # Password not required for regular user
        inputs = {"user_type": "user"}
        missing = validator.get_missing_required_parameters(conditional_parameters, inputs)
        assert len(missing) == 0, "Password should not be required for regular user"
        print("  PASS Conditional validation working")

        # Password required for admin
        inputs = {"user_type": "admin"}
        missing = validator.get_missing_required_parameters(conditional_parameters, inputs)
        assert len(missing) == 1, "Password should be required for admin"
        print("  PASS Conditional requirement working")

        return True

    except Exception as e:
        print(f"  FAIL Parameter validator test failed: {e}")
        return False

def test_enhanced_execution_state_manager():
    """Test the enhanced execution state manager"""
    print("\nTESTING: Enhanced Execution State Manager")

    try:
        from backend.core.enhanced_execution_state_manager import EnhancedExecutionStateManager
        from backend.core.advanced_workflow_system import WorkflowState

        manager = EnhancedExecutionStateManager()

        # Test workflow creation
        workflow_id = "test_workflow_001"
        workflow_data = {
            "workflow_id": workflow_id,
            "name": "Test Multi-Step Workflow",
            "description": "Test workflow for state management",
            "steps": [
                {"step_id": "step1", "name": "Input Collection"},
                {"step_id": "step2", "name": "Data Processing"},
                {"step_id": "step3", "name": "Output Generation"}
            ],
            "current_step": "step1",
            "state": "running"
        }

        # Create workflow state
        manager.create_workflow_state(workflow_id, workflow_data)
        print("  PASS Workflow state creation working")

        # Test step tracking
        current_step = manager.get_current_step(workflow_id)
        assert current_step == "step1", f"Expected step1, got {current_step}"
        print("  PASS Current step tracking working")

        # Test step completion
        manager.complete_step(workflow_id, "step1", {"collected_inputs": {"name": "test"}})
        manager.advance_to_step(workflow_id, "step2")

        current_step = manager.get_current_step(workflow_id)
        assert current_step == "step2", f"Expected step2, got {current_step}"
        print("  PASS Step advancement working")

        # Test pause/resume
        pause_data = manager.pause_workflow(workflow_id, "user_request", {"missing_params": ["api_key"]})
        assert pause_data["previous_state"] == "running", "Should preserve previous state"
        print("  PASS Workflow pause working")

        resume_data = manager.resume_workflow(workflow_id, {"api_key": "test_key"})
        assert resume_data["resumed_from"] == "paused", "Should track resume from paused"
        print("  PASS Workflow resume working")

        # Test multi-output aggregation
        outputs = [
            {"step_id": "step2", "output": {"processed_data": [1, 2, 3]}},
            {"step_id": "step3", "output": {"final_result": "success"}}
        ]

        manager.add_step_output(workflow_id, "step2", outputs[0]["output"])
        manager.add_step_output(workflow_id, "step3", outputs[1]["output"])

        aggregated = manager.get_aggregated_outputs(workflow_id)
        assert len(aggregated) == 2, f"Expected 2 outputs, got {len(aggregated)}"
        print("  PASS Multi-output aggregation working")

        # Test state persistence
        state = manager.get_workflow_state(workflow_id)
        assert state["workflow_id"] == workflow_id, "Should preserve workflow ID"
        assert state["current_step"] == "step2", "Should track current step"
        print("  PASS State persistence working")

        return True

    except Exception as e:
        print(f"  FAIL Enhanced state manager test failed: {e}")
        return False

def test_advanced_workflow_system():
    """Test the advanced workflow system"""
    print("\nTESTING: Advanced Workflow System")

    try:
        from backend.core.advanced_workflow_system import (
            AdvancedWorkflowDefinition,
            WorkflowStep,
            InputParameter,
            ParameterType,
            WorkflowState
        )

        # Create input parameters
        inputs = [
            InputParameter(
                name="user_name",
                type=ParameterType.STRING,
                label="User Name",
                description="User's full name",
                required=True,
                validation_rules={"length": {"min_length": 2}}
            ),
            InputParameter(
                name="email",
                type=ParameterType.STRING,
                label="Email Address",
                description="User's email address",
                required=True,
                show_when={"user_type": "admin"}
            )
        ]

        # Create workflow steps
        steps = [
            WorkflowStep(
                step_id="collect_input",
                name="Collect User Input",
                description="Gather user information",
                step_type="input_collection",
                input_parameters=inputs
            ),
            WorkflowStep(
                step_id="process_data",
                name="Process Data",
                description="Process the collected data",
                step_type="data_processing"
            )
        ]

        # Create workflow
        workflow = AdvancedWorkflowDefinition(
            workflow_id="test_multi_input_workflow",
            name="Multi-Input Test Workflow",
            description="Test workflow with multiple inputs",
            input_schema=inputs,
            steps=steps
        )

        assert workflow.workflow_id is not None, "Workflow should have ID"
        assert len(workflow.input_schema) == 2, "Should have 2 input parameters"
        assert len(workflow.steps) == 2, "Should have 2 steps"
        print("  PASS Workflow definition working")

        # Test parameter collection
        user_inputs = {"user_name": "John"}
        missing = workflow.get_missing_inputs(user_inputs)

        # Email should not be missing since user_type is not admin
        email_missing = any(param["name"] == "email" for param in missing)
        assert not email_missing, "Email should not be required when user_type is not admin"
        print("  PASS Conditional parameter logic working")

        # Test step advancement
        workflow.advance_to_step("process_data")
        assert workflow.current_step == "process_data", "Should advance to process_data"
        print("  PASS Step advancement working")

        # Test multi-output
        workflow.add_step_output("collect_input", {"user_data": {"name": "John"}})
        workflow.add_step_output("process_data", {"processed_result": "success"})

        outputs = workflow.get_all_outputs()
        assert len(outputs) == 2, "Should have 2 outputs"
        print("  PASS Multi-output tracking working")

        return True

    except Exception as e:
        print(f"  FAIL Advanced workflow system test failed: {e}")
        return False

def test_integration_workflow():
    """Test complete workflow integration"""
    print("\nTESTING: Complete Workflow Integration")

    try:
        from backend.core.enhanced_execution_state_manager import EnhancedExecutionStateManager
        from backend.core.workflow_parameter_validator import WorkflowParameterValidator
        from backend.core.advanced_workflow_system import (
            AdvancedWorkflowDefinition,
            WorkflowStep,
            InputParameter,
            ParameterType
        )

        # Initialize components
        state_manager = EnhancedExecutionStateManager()
        validator = WorkflowParameterValidator()

        # Create workflow
        inputs = [
            InputParameter(
                name="project_name",
                type=ParameterType.STRING,
                label="Project Name",
                description="Name of the project",
                required=True
            ),
            InputParameter(
                name="user_type",
                type=ParameterType.SELECT,
                label="User Type",
                description="Type of user account",
                required=True,
                options=["user", "admin"]
            ),
            InputParameter(
                name="admin_key",
                type=ParameterType.STRING,
                label="Admin Key",
                description="Admin authentication key",
                required=True,
                show_when={"user_type": "admin"}
            )
        ]

        steps = [
            WorkflowStep(
                step_id="validate_input",
                name="Validate Input",
                description="Validate user input",
                step_type="validation"
            ),
            WorkflowStep(
                step_id="process_project",
                name="Process Project",
                description="Process the project based on user type",
                step_type="processing"
            )
        ]

        workflow = AdvancedWorkflowDefinition(
            workflow_id="integration_test_workflow",
            name="Integration Test Workflow",
            description="Complete integration test",
            input_schema=inputs,
            steps=steps
        )

        workflow_id = workflow.workflow_id

        # Create workflow state
        state_manager.create_workflow_state(workflow_id, workflow.dict())
        print("  PASS Workflow state initialized")

        # Test with missing required parameters
        user_inputs = {"project_name": "Test Project"}
        missing = state_manager.get_missing_inputs(workflow_id, user_inputs)

        assert len(missing) >= 1, "Should have missing parameters"
        missing_names = [param["name"] for param in missing]
        assert "user_type" in missing_names, "user_type should be missing"
        print("  PASS Missing parameter detection working")

        # Test parameter validation
        param_schema = {param.name: param.dict() for param in inputs}
        validation_result = validator.validate_parameters(param_schema, user_inputs)

        assert not validation_result["valid"], "Should fail validation with missing user_type"
        print("  PASS Parameter validation working")

        # Test pause due to missing parameters
        pause_data = state_manager.pause_workflow(
            workflow_id,
            "missing_parameters",
            {"missing_params": missing_names}
        )

        assert pause_data["reason"] == "missing_parameters", "Should track pause reason"
        print("  PASS Pause for missing parameters working")

        # Test resume with complete parameters
        complete_inputs = {
            "project_name": "Test Project",
            "user_type": "user"
        }

        resume_data = state_manager.resume_workflow(workflow_id, complete_inputs)
        assert resume_data["success"], "Should resume successfully"
        print("  PASS Resume with complete inputs working")

        # Test multi-step execution
        state_manager.complete_step(workflow_id, "validate_input", {"validated": True})
        state_manager.advance_to_step(workflow_id, "process_project")

        # Add outputs from both steps
        state_manager.add_step_output(workflow_id, "validate_input", {"validation_status": "passed"})
        state_manager.add_step_output(workflow_id, "process_project", {"project_status": "processed"})

        # Test output aggregation
        outputs = state_manager.get_aggregated_outputs(workflow_id)
        assert len(outputs) == 2, "Should have outputs from both steps"
        print("  PASS Multi-step output aggregation working")

        # Test final workflow completion
        state_manager.complete_workflow(workflow_id, "success")
        final_state = state_manager.get_workflow_state(workflow_id)

        assert final_state["status"] == "success", "Workflow should be completed successfully"
        print("  PASS Workflow completion working")

        return True

    except Exception as e:
        print(f"  FAIL Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test runner"""
    print("="*80)
    print("WORKFLOW SYSTEM FUNCTIONALITY TESTS")
    print("="*80)
    print(f"Started: {datetime.now().isoformat()}")

    test_results = []

    # Run individual component tests
    test_results.append(("Parameter Validator", test_workflow_parameter_validator()))
    test_results.append(("Enhanced State Manager", test_enhanced_execution_state_manager()))
    test_results.append(("Advanced Workflow System", test_advanced_workflow_system()))
    test_results.append(("Complete Integration", test_integration_workflow()))

    # Summary
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)

    for test_name, result in test_results:
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<50} {status}")

    print(f"\nOverall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"Completed: {datetime.now().isoformat()}")
    print("="*80)

    # Exit with appropriate code
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()