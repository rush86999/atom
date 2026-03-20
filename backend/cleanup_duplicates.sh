#!/bin/bash
# Auto-generated cleanup script for duplicate test files
# Review before executing!

set -e

echo "Cleaning up duplicate test files..."
echo "Total files to delete: 88"


# test_agent_context_resolver.py
# Keeping: tests/unit/governance/test_agent_context_resolver.py
git rm "tests/test_agent_context_resolver.py"
git rm "tests/unit/agent/test_agent_context_resolver.py"

# test_agent_coordination_invariants.py
# Keeping: tests/property_tests/multi_agent/test_agent_coordination_invariants.py
git rm "tests/property_tests/agents/test_agent_coordination_invariants.py"
git rm "tests/property_tests/agent/test_agent_coordination_invariants.py"

# test_agent_execution_orchestration.py
# Keeping: tests/integration/test_agent_execution_orchestration.py
git rm "tests/integration/agent/test_agent_execution_orchestration.py"

# test_agent_governance_invariants.py
# Keeping: tests/property_tests/agent/test_agent_governance_invariants.py
git rm "tests/property_tests/governance/test_agent_governance_invariants.py"

# test_agent_governance_routes.py
# Keeping: tests/api/test_agent_governance_routes.py
git rm "tests/integration/test_agent_governance_routes.py"

# test_agent_governance_service.py
# Keeping: tests/unit/test_agent_governance_service.py
git rm "tests/test_agent_governance_service.py"
git rm "tests/unit/agent/test_agent_governance_service.py"

# test_agent_graduation_service.py
# Keeping: tests/property/test_agent_graduation_service.py
git rm "tests/unit/agent/test_agent_graduation_service.py"
git rm "tests/unit/episodes/test_agent_graduation_service.py"

# test_agent_graduation_service_coverage.py
# Keeping: tests/core/agents/test_agent_graduation_service_coverage.py
git rm "tests/core/test_agent_graduation_service_coverage.py"

# test_agent_guidance_routes.py
# Keeping: tests/api/test_agent_guidance_routes.py
git rm "tests/unit/test_agent_guidance_routes.py"

# test_agent_social_layer_coverage.py
# Keeping: tests/core/agents/test_agent_social_layer_coverage.py
git rm "tests/core/test_agent_social_layer_coverage.py"

# test_api_contracts.py
# Keeping: tests/property_tests/api/test_api_contracts.py
git rm "tests/test_api_contracts.py"

# test_atom_agent_endpoints.py
# Keeping: tests/api/test_atom_agent_endpoints.py
git rm "tests/unit/test_atom_agent_endpoints.py"
git rm "tests/integration/test_atom_agent_endpoints.py"

# test_atom_agent_endpoints_coverage.py
# Keeping: tests/api/test_atom_agent_endpoints_coverage.py
git rm "tests/core/agents/test_atom_agent_endpoints_coverage.py"
git rm "tests/core/agent_endpoints/test_atom_agent_endpoints_coverage.py"

# test_auth_flows.py
# Keeping: tests/security/test_auth_flows.py
git rm "tests/integration/test_auth_flows.py"

# test_auth_login.py
# Keeping: tests/security/test_auth_login.py
git rm "tests/e2e_ui/tests/test_auth_login.py"

# test_auth_logout.py
# Keeping: tests/security/test_auth_logout.py
git rm "tests/e2e_ui/tests/test_auth_logout.py"

# test_browser_routes.py
# Keeping: tests/api/test_browser_routes.py
git rm "tests/integration/test_browser_routes.py"

# test_browser_tool.py
# Keeping: tests/unit/test_browser_tool.py
git rm "tests/unit/tools/test_browser_tool.py"
git rm "tests/test_browser_tool.py"

# test_budget_guardrails.py
# Keeping: tests/unit/budget/test_budget_guardrails.py
git rm "tests/test_budget_guardrails.py"

# test_business_facts_routes.py
# Keeping: tests/api/test_business_facts_routes.py
git rm "tests/test_business_facts_routes.py"

# test_byok_handler.py
# Keeping: tests/unit/test_byok_handler.py
git rm "tests/test_byok_handler.py"
git rm "tests/unit/llm/test_byok_handler.py"

# test_byok_handler_coverage.py
# Keeping: tests/core/llm/test_byok_handler_coverage.py
git rm "tests/unit/llm/test_byok_handler_coverage.py"

# test_byok_handler_integration.py
# Keeping: tests/integration/test_byok_handler_integration.py
git rm "tests/test_byok_handler_integration.py"

# test_canvas_forms.py
# Keeping: tests/e2e_ui/tests/test_canvas_forms.py
git rm "tests/integration/canvas/test_canvas_forms.py"

# test_canvas_tool.py
# Keeping: tests/unit/test_canvas_tool.py
git rm "tests/unit/tools/test_canvas_tool.py"
git rm "tests/test_canvas_tool.py"

# test_canvas_tool_coverage.py
# Keeping: tests/tools/test_canvas_tool_coverage.py
git rm "tests/unit/canvas/test_canvas_tool_coverage.py"

# test_cognitive_tier_routes.py
# Keeping: tests/api/test_cognitive_tier_routes.py
git rm "tests/integration/test_cognitive_tier_routes.py"

# test_cognitive_tier_service.py
# Keeping: tests/property/test_cognitive_tier_service.py
git rm "tests/test_cognitive_tier_service.py"

# test_config_coverage.py
# Keeping: tests/core/test_config_coverage.py
git rm "tests/core/systems/test_config_coverage.py"

# test_coverage_aggregation.py
# Keeping: tests/coverage/test_coverage_aggregation.py
git rm "tests/integration/test_coverage_aggregation.py"

# test_data_factory.py
# Keeping: tests/e2e_ui/fixtures/test_data_factory.py
git rm "tests/e2e/fixtures/test_data_factory.py"

# test_device_tool.py
# Keeping: tests/unit/test_device_tool.py
git rm "tests/unit/tools/test_device_tool.py"
git rm "tests/test_device_tool.py"

# test_double_entry_invariants.py
# Keeping: tests/property_tests/financial/test_double_entry_invariants.py
git rm "tests/property_tests/accounting/test_double_entry_invariants.py"

# test_episode_invariants.py
# Keeping: tests/property_tests/episodes/test_episode_invariants.py
git rm "tests/test_episode_invariants.py"

# test_episode_lifecycle_coverage.py
# Keeping: tests/core/episodes/test_episode_lifecycle_coverage.py
git rm "tests/unit/episodes/test_episode_lifecycle_coverage.py"

# test_episode_lifecycle_service.py
# Keeping: tests/unit/episodes/test_episode_lifecycle_service.py
git rm "tests/test_episode_lifecycle_service.py"

# test_episode_performance.py
# Keeping: tests/integration/performance/test_episode_performance.py
git rm "tests/test_episode_performance.py"

# test_episode_retrieval_coverage.py
# Keeping: tests/core/episodes/test_episode_retrieval_coverage.py
git rm "tests/unit/episodes/test_episode_retrieval_coverage.py"

# test_episode_retrieval_service.py
# Keeping: tests/unit/episodes/test_episode_retrieval_service.py
git rm "tests/test_episode_retrieval_service.py"

# test_episode_segmentation.py
# Keeping: tests/unit/test_episode_segmentation.py
git rm "tests/test_episode_segmentation.py"

# test_episode_segmentation_coverage.py
# Keeping: tests/core/episodes/test_episode_segmentation_coverage.py
git rm "tests/unit/episodes/test_episode_segmentation_coverage.py"

# test_episode_segmentation_service.py
# Keeping: tests/unit/episodes/test_episode_segmentation_service.py
git rm "tests/test_episode_segmentation_service.py"

# test_escalation_manager.py
# Keeping: tests/property/test_escalation_manager.py
git rm "tests/unit/llm/test_escalation_manager.py"
git rm "tests/test_escalation_manager.py"

# test_feedback_enhanced.py
# Keeping: tests/api/test_feedback_enhanced.py
git rm "tests/test_feedback_enhanced.py"

# test_financial_invariants.py
# Keeping: tests/property_tests/financial/test_financial_invariants.py
git rm "tests/test_financial_invariants.py"

# test_flaky_detection.py
# Keeping: tests/e2e_ui/tests/unit/test_flaky_detection.py
git rm "tests/test_flaky_detection.py"

# test_governance_cache.py
# Keeping: tests/unit/agent/test_governance_cache.py
git rm "tests/test_governance_cache.py"

# test_governance_invariants.py
# Keeping: tests/property_tests/agent_governance/test_governance_invariants.py
git rm "tests/property_tests/governance/test_governance_invariants.py"
git rm "tests/test_governance_invariants.py"

# test_governance_performance.py
# Keeping: tests/integration/performance/test_governance_performance.py
git rm "tests/test_governance_performance.py"

# test_health_routes.py
# Keeping: tests/api/test_health_routes.py
git rm "tests/test_health_routes.py"

# test_integration_dashboard_routes.py
# Keeping: tests/api/test_integration_dashboard_routes.py
git rm "tests/unit/test_integration_dashboard_routes.py"

# test_multi_agent_coordination_invariants.py
# Keeping: tests/property_tests/governance/test_multi_agent_coordination_invariants.py
git rm "tests/property_tests/multi_agent/test_multi_agent_coordination_invariants.py"

# test_oauth_flows.py
# Keeping: tests/security/test_oauth_flows.py
git rm "tests/security/oauth/test_oauth_flows.py"

# test_productivity_routes_coverage.py
# Keeping: tests/api/test_productivity_routes_coverage.py
git rm "tests/core/test_productivity_routes_coverage.py"

# test_prompt_injection.py
# Keeping: tests/security_edge_cases/test_prompt_injection.py
git rm "tests/security/test_prompt_injection.py"

# test_proposal_service.py
# Keeping: tests/property/test_proposal_service.py
git rm "tests/unit/governance/test_proposal_service.py"

# test_route_registration.py
# Keeping: tests/standalone/test_route_registration.py
git rm "tests/integration/test_route_registration.py"
git rm "tests/integration/config/test_route_registration.py"

# test_security_invariants.py
# Keeping: tests/property_tests/security/test_security_invariants.py
git rm "tests/test_security_invariants.py"

# test_session_management_invariants.py
# Keeping: tests/property_tests/session_management/test_session_management_invariants.py
git rm "tests/property_tests/sessions/test_session_management_invariants.py"

# test_skill_registry_service_coverage.py
# Keeping: tests/core/skills/test_skill_registry_service_coverage.py
git rm "tests/core/test_skill_registry_service_coverage.py"

# test_student_training_service.py
# Keeping: tests/unit/governance/test_student_training_service.py
git rm "tests/test_student_training_service.py"
git rm "tests/unit/agent/test_student_training_service.py"

# test_student_training_service_coverage.py
# Keeping: tests/core/systems/test_student_training_service_coverage.py
git rm "tests/core/test_student_training_service_coverage.py"

# test_supervision_service.py
# Keeping: tests/property/test_supervision_service.py
git rm "tests/unit/governance/test_supervision_service.py"
git rm "tests/test_supervision_service.py"

# test_time_travel_routes.py
# Keeping: tests/api/test_time_travel_routes.py
git rm "tests/unit/api/test_time_travel_routes.py"

# test_trigger_interceptor.py
# Keeping: tests/unit/governance/test_trigger_interceptor.py
git rm "tests/test_trigger_interceptor.py"

# test_validation_service.py
# Keeping: tests/unit/security/test_validation_service.py
git rm "tests/test_validation_service.py"

# test_websocket_routes.py
# Keeping: tests/api/test_websocket_routes.py
git rm "tests/unit/api/test_websocket_routes.py"

# test_workflow_debugger_coverage.py
# Keeping: tests/core/test_workflow_debugger_coverage.py
git rm "tests/core/workflow/test_workflow_debugger_coverage.py"

# test_workflow_engine_coverage.py
# Keeping: tests/core/test_workflow_engine_coverage.py
git rm "tests/test_workflow_engine_coverage.py"
git rm "tests/core/workflow/test_workflow_engine_coverage.py"

# test_workflow_engine_integration.py
# Keeping: tests/integration/test_workflow_engine_integration.py
git rm "tests/test_workflow_engine_integration.py"

# test_workflow_engine_state_invariants.py
# Keeping: tests/property_tests/workflow/test_workflow_engine_state_invariants.py
git rm "tests/property_tests/workflows/test_workflow_engine_state_invariants.py"

# test_workflow_template_system_coverage.py
# Keeping: tests/core/workflow/test_workflow_template_system_coverage.py
git rm "tests/core/test_workflow_template_system_coverage.py"

echo "Cleanup complete!"
echo "Run: git status to review changes"
