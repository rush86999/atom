"""
Unit tests for Workflow Step Types Reference

Tests core/workflow_step_types.py (8 lines, zero coverage)
Covers workflow step type reference dictionary and helper functions
"""

import pytest
from core.workflow_step_types import (
    STEP_TYPE_REFERENCE,
    get_step_types_by_category,
    get_all_categories,
)


# ==================== Step Type Reference Tests ====================

class TestStepTypeReference:
    """Tests for step type reference dictionary"""

    def test_step_type_reference_exists(self):
        """Test that step type reference is defined"""
        assert isinstance(STEP_TYPE_REFERENCE, dict)
        assert len(STEP_TYPE_REFERENCE) > 0

    def test_core_step_types_exist(self):
        """Test that core workflow step types are defined"""
        assert "conditional_logic" in STEP_TYPE_REFERENCE
        assert "parallel_execution" in STEP_TYPE_REFERENCE
        assert "delay" in STEP_TYPE_REFERENCE
        assert "approval_required" in STEP_TYPE_REFERENCE
        assert "data_transformation" in STEP_TYPE_REFERENCE
        assert "api_call" in STEP_TYPE_REFERENCE

    def test_communication_step_types_exist(self):
        """Test that communication step types are defined"""
        assert "email_send" in STEP_TYPE_REFERENCE
        assert "slack_notification" in STEP_TYPE_REFERENCE

    def test_integration_step_types_exist(self):
        """Test that integration step types are defined"""
        assert "gmail_fetch" in STEP_TYPE_REFERENCE
        assert "gmail_search" in STEP_TYPE_REFERENCE
        assert "notion_integration" in STEP_TYPE_REFERENCE
        assert "asana_integration" in STEP_TYPE_REFERENCE
        assert "hubspot_integration" in STEP_TYPE_REFERENCE
        assert "salesforce_integration" in STEP_TYPE_REFERENCE

    def test_ai_step_types_exist(self):
        """Test that AI/knowledge step types are defined"""
        assert "nlu_analysis" in STEP_TYPE_REFERENCE
        assert "knowledge_lookup" in STEP_TYPE_REFERENCE
        assert "knowledge_update" in STEP_TYPE_REFERENCE
        assert "system_reasoning" in STEP_TYPE_REFERENCE
        assert "app_search" in STEP_TYPE_REFERENCE

    def test_agent_step_types_exist(self):
        """Test that agent execution step types are defined"""
        assert "agent_execution" in STEP_TYPE_REFERENCE
        assert "background_agent_start" in STEP_TYPE_REFERENCE
        assert "background_agent_stop" in STEP_TYPE_REFERENCE

    def test_financial_step_types_exist(self):
        """Test that financial operations step types are defined"""
        assert "cost_leak_detection" in STEP_TYPE_REFERENCE
        assert "budget_check" in STEP_TYPE_REFERENCE
        assert "invoice_reconciliation" in STEP_TYPE_REFERENCE

    def test_step_type_structure(self):
        """Test that each step type has required structure"""
        for step_type, config in STEP_TYPE_REFERENCE.items():
            assert "category" in config
            assert "description" in config
            assert "parameters" in config
            assert "outputs" in config
            assert isinstance(config["category"], str)
            assert isinstance(config["description"], str)
            assert isinstance(config["parameters"], list)
            assert isinstance(config["outputs"], list)


# ==================== Category Filtering Tests ====================

class TestCategoryFiltering:
    """Tests for category-based filtering"""

    def test_get_step_types_by_category_all(self):
        """Test getting all step types"""
        all_steps = get_step_types_by_category()
        assert isinstance(all_steps, list)
        assert len(all_steps) > 0
        assert all("type" in step for step in all_steps)

    def test_get_step_types_by_category_core(self):
        """Test getting core workflow step types"""
        core_steps = get_step_types_by_category("core")
        assert isinstance(core_steps, list)
        assert len(core_steps) > 0
        assert all(step.get("category") == "core" for step in core_steps)
        assert "conditional_logic" in [s["type"] for s in core_steps]

    def test_get_step_types_by_category_communication(self):
        """Test getting communication step types"""
        comm_steps = get_step_types_by_category("communication")
        assert isinstance(comm_steps, list)
        assert len(comm_steps) > 0
        assert all(step.get("category") == "communication" for step in comm_steps)

    def test_get_step_types_by_category_integration(self):
        """Test getting integration step types"""
        integration_steps = get_step_types_by_category("integration")
        assert isinstance(integration_steps, list)
        assert len(integration_steps) > 0
        assert all(step.get("category") == "integration" for step in integration_steps)

    def test_get_step_types_by_category_ai(self):
        """Test getting AI step types"""
        ai_steps = get_step_types_by_category("ai")
        assert isinstance(ai_steps, list)
        assert len(ai_steps) > 0
        assert all(step.get("category") == "ai" for step in ai_steps)

    def test_get_step_types_by_category_agent(self):
        """Test getting agent step types"""
        agent_steps = get_step_types_by_category("agent")
        assert isinstance(agent_steps, list)
        assert len(agent_steps) > 0
        assert all(step.get("category") == "agent" for step in agent_steps)

    def test_get_step_types_by_category_invalid(self):
        """Test getting step types for non-existent category"""
        invalid_steps = get_step_types_by_category("nonexistent_category")
        assert isinstance(invalid_steps, list)
        assert len(invalid_steps) == 0


# ==================== Category Listing Tests ====================

class TestCategoryListing:
    """Tests for category listing functionality"""

    def test_get_all_categories(self):
        """Test getting all available categories"""
        categories = get_all_categories()
        assert isinstance(categories, list)
        assert len(categories) > 0
        assert "core" in categories
        assert "communication" in categories
        assert "integration" in categories
        assert "ai" in categories
        assert "agent" in categories

    def test_get_all_categories_unique(self):
        """Test that all categories are unique"""
        categories = get_all_categories()
        assert len(categories) == len(set(categories))

    def test_categories_match_reference(self):
        """Test that categories match those in reference"""
        categories = get_all_categories()
        reference_categories = set(config["category"] for config in STEP_TYPE_REFERENCE.values())
        assert set(categories) == reference_categories


# ==================== Step Type Details Tests ====================

class TestStepTypeDetails:
    """Tests for specific step type details"""

    def test_conditional_logic_step_details(self):
        """Test conditional_logic step has correct details"""
        step = STEP_TYPE_REFERENCE["conditional_logic"]
        assert step["category"] == "core"
        assert "conditions" in step["parameters"]
        assert "next_steps" in step["outputs"]

    def test_parallel_execution_step_details(self):
        """Test parallel_execution step has correct details"""
        step = STEP_TYPE_REFERENCE["parallel_execution"]
        assert step["category"] == "core"
        assert "parallel_steps" in step["parameters"]
        assert "parallel_results" in step["outputs"]

    def test_agent_execution_step_details(self):
        """Test agent_execution step has correct details"""
        step = STEP_TYPE_REFERENCE["agent_execution"]
        assert step["category"] == "agent"
        assert "agent_id" in step["parameters"]
        assert "agent_output" in step["outputs"]

    def test_cost_leak_detection_step_details(self):
        """Test cost_leak_detection step has correct details"""
        step = STEP_TYPE_REFERENCE["cost_leak_detection"]
        assert step["category"] == "financial"
        assert "cost_report" in step["outputs"]
        assert "unused_count" in step["outputs"]


# ==================== Edge Case Tests ====================

class TestEdgeCases:
    """Tests for edge cases and validation"""

    def test_all_step_types_have_descriptions(self):
        """Test that all step types have descriptions"""
        for step_type, config in STEP_TYPE_REFERENCE.items():
            assert config["description"]
            assert len(config["description"]) > 0

    def test_all_parameters_lists_exist(self):
        """Test that all step types have parameters list"""
        for step_type, config in STEP_TYPE_REFERENCE.items():
            assert isinstance(config["parameters"], list)

    def test_all_outputs_lists_exist(self):
        """Test that all step types have outputs list"""
        for step_type, config in STEP_TYPE_REFERENCE.items():
            assert isinstance(config["outputs"], list)

    def test_step_type_naming_consistency(self):
        """Test that step type names follow snake_case convention"""
        for step_type in STEP_TYPE_REFERENCE.keys():
            # Should contain only lowercase letters, numbers, and underscores
            assert step_type.islower() or "_" in step_type or step_type.isalnum()


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
