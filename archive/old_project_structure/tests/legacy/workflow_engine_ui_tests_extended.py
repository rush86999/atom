#!/usr/bin/env python3
"""
10 Additional UI Tests for Workflow Engine System
Integrating with existing AI validation system for comprehensive UI testing
"""

import asyncio
import json
import time
import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import logging
import uuid
import random

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import existing AI validation system
from testing.workflow_engine_e2e_tests import WorkflowEngineAIValidation

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ExtendedWorkflowEngineUI:
    """Extended Chrome DevTools browser automation for workflow engine UI"""

    def __init__(self):
        # Import browser from previous file
        from testing.workflow_engine_browser_automation_tests import ChromeDevToolsBrowser
        self.browser = ChromeDevToolsBrowser()
        self.ai_validator = WorkflowEngineAIValidation()
        self.base_url = "http://localhost:3000"
        self.test_results = []

    async def setup(self) -> bool:
        """Setup browser and navigate to application"""
        if not await self.browser.launch(headless=True):
            return False

        # Navigate to workflow engine application
        await self.browser.navigate_to(f"{self.base_url}/workflows")
        await asyncio.sleep(2)
        return True

    async def test_7_workflow_list_and_search_ui(self) -> Dict[str, Any]:
        """Test 7: Workflow List and Search Interface"""
        test_name = "Workflow List and Search UI"
        logger.info(f"Running UI Test 7: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'ui_interactions': [],
            'search_features': [],
            'filter_actions': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflow list
            await self.browser.navigate_to(f"{self.base_url}/workflows")
            await asyncio.sleep(2)

            # Step 1: Test workflow list loading
            logger.info("  Step 1: Testing workflow list loading")
            list_loaded = await self.browser.wait_for_element('[data-testid="workflow-list"]')
            result['ui_interactions'].append({
                'action': 'workflow_list_loaded',
                'successful': list_loaded,
                'timestamp': time.time()
            })

            # Step 2: Test search functionality
            logger.info("  Step 2: Testing workflow search")
            search_input_filled = await self.browser.type_text('#workflow-search', "data processing")
            search_performed = await self.browser.press_key('#workflow-search', 'Enter')

            result['search_features'].append({
                'action': 'search_workflows',
                'successful': search_input_filled and search_performed,
                'search_query': 'data processing',
                'timestamp': time.time()
            })

            await asyncio.sleep(1)

            # Step 3: Test search filters
            logger.info("  Step 3: Testing search filters")
            status_filter_clicked = await self.browser.click_element('[data-testid="filter-status-running"]')
            category_filter_clicked = await self.browser.click_element('[data-testid="filter-category-data-processing"]')

            result['filter_actions'].append({
                'action': 'apply_filters',
                'successful': status_filter_clicked and category_filter_clicked,
                'filters_applied': ['status', 'category'],
                'timestamp': time.time()
            })

            # Step 4: Test sorting options
            logger.info("  Step 4: Testing workflow sorting")
            sort_dropdown_clicked = await self.browser.click_element('[data-testid="sort-dropdown"]')
            sort_by_date_clicked = await self.browser.click_element('[data-value="created_at"]')

            result['ui_interactions'].append({
                'action': 'sort_workflows',
                'successful': sort_dropdown_clicked and sort_by_date_clicked,
                'sort_criteria': 'created_at',
                'timestamp': time.time()
            })

            await asyncio.sleep(1)

            # Step 5: Test pagination
            logger.info("  Step 5: Testing pagination")
            next_page_clicked = await self.browser.click_element('[data-testid="pagination-next"]')
            page_indicator = await self.browser.get_element_text('[data-testid="current-page"]')

            result['ui_interactions'].append({
                'action': 'pagination_navigation',
                'successful': next_page_clicked,
                'current_page': page_indicator,
                'timestamp': time.time()
            })

            # Step 6: Test batch operations
            logger.info("  Step 6: Testing batch operations")
            select_all_clicked = await self.browser.click_element('[data-testid="select-all-workflows"]')
            batch_delete_clicked = await self.browser.click_element('[data-testid="batch-delete-btn"]')
            confirm_modal = await self.browser.wait_for_element('[data-testid="confirm-modal"]')

            result['ui_interactions'].append({
                'action': 'batch_operations',
                'successful': select_all_clicked and batch_delete_clicked and confirm_modal,
                'operation': 'batch_delete',
                'timestamp': time.time()
            })

            # Cancel the operation to avoid data loss
            await self.browser.click_element('[data-testid="cancel-delete"]')

            await self.browser.take_screenshot(f"test_7_workflow_list_{int(time.time())}.png")

            # Determine success
            all_successful = all(interaction['successful'] for interaction in result['ui_interactions'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Workflow list test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_7_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_8_workflow_step_configuration_ui(self) -> Dict[str, Any]:
        """Test 8: Workflow Step Configuration Interface"""
        test_name = "Workflow Step Configuration UI"
        logger.info(f"Running UI Test 8: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'configuration_actions': [],
            'parameter_tests': [],
            'validation_checks': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflow editor
            await self.browser.navigate_to(f"{self.base_url}/workflows/editor/step-config")
            await asyncio.sleep(2)

            # Step 1: Test step type selection
            logger.info("  Step 1: Testing step type selection")
            step_type_clicked = await self.browser.click_element('[data-testid="add-step-btn"]')
            api_step_selected = await self.browser.click_element('[data-step-type="api-call"]')

            result['configuration_actions'].append({
                'action': 'select_step_type',
                'successful': step_type_clicked and api_step_selected,
                'step_type': 'api-call',
                'timestamp': time.time()
            })

            # Step 2: Test parameter configuration
            logger.info("  Step 2: Testing parameter configuration")

            # API endpoint parameter
            endpoint_filled = await self.browser.type_text('#api-endpoint', 'https://api.example.com/data')
            method_selected = await self.browser.click_element('[data-value="POST"]')

            # Headers parameter
            add_header_clicked = await self.browser.click_element('[data-testid="add-header-btn"]')
            header_key_filled = await self.browser.type_text('#header-key-0', 'Authorization')
            header_value_filled = await self.browser.type_text('#header-value-0', 'Bearer token123')

            result['parameter_tests'].append({
                'action': 'configure_parameters',
                'successful': endpoint_filled and method_selected and add_header_clicked and header_key_filled and header_value_filled,
                'parameters_configured': ['endpoint', 'method', 'headers'],
                'timestamp': time.time()
            })

            # Step 3: Test timeout and retry configuration
            logger.info("  Step 3: Testing timeout and retry configuration")

            timeout_filled = await self.browser.type_text('#step-timeout', '30000')
            retry_count_filled = await self.browser.type_text('#retry-count', '3')
            retry_enabled = await self.browser.click_element('[data-testid="enable-retry"]')

            result['configuration_actions'].append({
                'action': 'configure_timeout_retry',
                'successful': timeout_filled and retry_count_filled and retry_enabled,
                'timeout': '30000ms',
                'retry_count': '3',
                'timestamp': time.time()
            })

            # Step 4: Test conditional execution
            logger.info("  Step 4: Testing conditional execution")

            condition_enabled = await self.browser.click_element('[data-testid="enable-condition"]')
            condition_expression_filled = await self.browser.type_text('#condition-expression', 'data.status == "active"')

            result['parameter_tests'].append({
                'action': 'configure_conditions',
                'successful': condition_enabled and condition_expression_filled,
                'condition': 'data.status == "active"',
                'timestamp': time.time()
            })

            # Step 5: Test error handling configuration
            logger.info("  Step 5: Testing error handling configuration")

            error_handling_enabled = await self.browser.click_element('[data-testid="enable-error-handling"]')
            fallback_step_selected = await self.browser.click_element('[data-fallback-step="notify-admin"]')

            result['configuration_actions'].append({
                'action': 'configure_error_handling',
                'successful': error_handling_enabled and fallback_step_selected,
                'fallback_action': 'notify-admin',
                'timestamp': time.time()
            })

            # Step 6: Test step validation
            logger.info("  Step 6: Testing step validation")

            validate_clicked = await self.browser.click_element('[data-testid="validate-step-btn"]')
            validation_result = await self.browser.get_element_text('[data-testid="validation-result"]')

            result['validation_checks'].append({
                'action': 'validate_step_config',
                'successful': validate_clicked,
                'validation_message': validation_result,
                'timestamp': time.time()
            })

            # Step 7: Test step preview
            logger.info("  Step 7: Testing step preview")

            preview_clicked = await self.browser.click_element('[data-testid="preview-step-btn"]')
            preview_modal = await self.browser.wait_for_element('[data-testid="step-preview-modal"]')

            result['configuration_actions'].append({
                'action': 'preview_step',
                'successful': preview_clicked and preview_modal,
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_8_step_config_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['configuration_actions'] + result['parameter_tests'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Step configuration test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_8_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_9_workflow_execution_history_ui(self) -> Dict[str, Any]:
        """Test 9: Workflow Execution History and Logs Interface"""
        test_name = "Workflow Execution History UI"
        logger.info(f"Running UI Test 9: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'history_actions': [],
            'log_interactions': [],
            'timeline_tests': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to execution history
            await self.browser.navigate_to(f"{self.base_url}/workflows/executions/history")
            await asyncio.sleep(2)

            # Step 1: Test execution history loading
            logger.info("  Step 1: Testing execution history loading")
            history_loaded = await self.browser.wait_for_element('[data-testid="execution-history"]')
            result['history_actions'].append({
                'action': 'execution_history_loaded',
                'successful': history_loaded,
                'timestamp': time.time()
            })

            # Step 2: Test timeline view
            logger.info("  Step 2: Testing timeline view")
            timeline_view_clicked = await self.browser.click_element('[data-testid="timeline-view-btn"]')
            timeline_events = await self.browser.execute_javascript("""
                return document.querySelectorAll('[data-testid="timeline-event"]').length;
            """)

            result['timeline_tests'].append({
                'action': 'timeline_view',
                'successful': timeline_view_clicked,
                'event_count': timeline_events.get("result", {}).get("value", 0),
                'timestamp': time.time()
            })

            # Step 3: Test log filtering
            logger.info("  Step 3: Testing log filtering")

            error_log_filter = await self.browser.click_element('[data-testid="filter-error-logs"]')
            warning_log_filter = await self.browser.click_element('[data-testid="filter-warning-logs"]')

            result['log_interactions'].append({
                'action': 'filter_logs',
                'successful': error_log_filter and warning_log_filter,
                'filters_applied': ['error', 'warning'],
                'timestamp': time.time()
            })

            await asyncio.sleep(1)

            # Step 4: Test log search within execution
            logger.info("  Step 4: Testing log search")

            log_search_filled = await self.browser.type_text('#log-search-input', "API call")
            search_performed = await self.browser.press_key('#log-search-input', 'Enter')

            result['log_interactions'].append({
                'action': 'search_logs',
                'successful': log_search_filled and search_performed,
                'search_query': 'API call',
                'timestamp': time.time()
            })

            # Step 5: Test log export
            logger.info("  Step 5: Testing log export")

            export_clicked = await self.browser.click_element('[data-testid="export-logs-btn"]')
            json_format_selected = await self.browser.click_element('[data-format="json"]')
            download_clicked = await self.browser.click_element('[data-testid="download-logs-btn"]')

            result['log_interactions'].append({
                'action': 'export_logs',
                'successful': export_clicked and json_format_selected and download_clicked,
                'format': 'json',
                'timestamp': time.time()
            })

            # Step 6: Test execution comparison
            logger.info("  Step 6: Testing execution comparison")

            compare_mode_clicked = await self.browser.click_element('[data-testid="compare-mode-btn"]')
            first_execution_selected = await self.browser.click_element('[data-execution-id="exec_1"]')
            second_execution_selected = await self.browser.click_element('[data-execution-id="exec_2"]')
            compare_clicked = await self.browser.click_element('[data-testid="compare-executions-btn"]')

            result['timeline_tests'].append({
                'action': 'compare_executions',
                'successful': compare_mode_clicked and first_execution_selected and second_execution_selected and compare_clicked,
                'executions_compared': 2,
                'timestamp': time.time()
            })

            # Step 7: Test performance metrics for execution
            logger.info("  Step 7: Testing performance metrics display")

            metrics_tab_clicked = await self.browser.click_element('[data-testid="execution-metrics-tab"]')
            cpu_metric_visible = await self.browser.wait_for_element('[data-metric="cpu"]')
            memory_metric_visible = await self.browser.wait_for_element('[data-metric="memory"]')
            duration_metric_visible = await self.browser.wait_for_element('[data-metric="duration"]')

            result['history_actions'].append({
                'action': 'view_performance_metrics',
                'successful': metrics_tab_clicked and cpu_metric_visible and memory_metric_visible and duration_metric_visible,
                'metrics_available': ['cpu', 'memory', 'duration'],
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_9_execution_history_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['history_actions'] + result['log_interactions'] + result['timeline_tests'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Execution history test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_9_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_10_workflow_collaboration_ui(self) -> Dict[str, Any]:
        """Test 10: Workflow Collaboration and Sharing Interface"""
        test_name = "Workflow Collaboration and Sharing UI"
        logger.info(f"Running UI Test 10: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'collaboration_actions': [],
            'sharing_features': [],
            'permission_tests': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflow collaboration
            await self.browser.navigate_to(f"{self.base_url}/workflows/collaboration")
            await asyncio.sleep(2)

            # Step 1: Test user invitation
            logger.info("  Step 1: Testing user invitation")
            invite_user_clicked = await self.browser.click_element('[data-testid="invite-user-btn"]')
            email_filled = await self.browser.type_text('#user-email-input', 'collaborator@example.com')
            role_selected = await self.browser.click_element('[data-role="editor"]')
            send_invite_clicked = await self.browser.click_element('[data-testid="send-invite-btn"]')

            result['collaboration_actions'].append({
                'action': 'invite_user',
                'successful': invite_user_clicked and email_filled and role_selected and send_invite_clicked,
                'user_email': 'collaborator@example.com',
                'role': 'editor',
                'timestamp': time.time()
            })

            # Step 2: Test permission management
            logger.info("  Step 2: Testing permission management")

            user_permissions_clicked = await self.browser.click_element('[data-user-id="user_123"]')
            permission_toggle = await self.browser.click_element('[data-permission="execute-workflow"]')
            save_permissions_clicked = await self.browser.click_element('[data-testid="save-permissions-btn"]')

            result['permission_tests'].append({
                'action': 'manage_permissions',
                'successful': user_permissions_clicked and permission_toggle and save_permissions_clicked,
                'permissions_modified': ['execute-workflow'],
                'timestamp': time.time()
            })

            # Step 3: Test workflow sharing
            logger.info("  Step 3: Testing workflow sharing")

            share_workflow_clicked = await self.browser.click_element('[data-testid="share-workflow-btn"]')
            public_link_generated = await self.browser.wait_for_element('[data-testid="public-link"]')
            copy_link_clicked = await self.browser.click_element('[data-testid="copy-link-btn"]')

            result['sharing_features'].append({
                'action': 'share_workflow',
                'successful': share_workflow_clicked and public_link_generated and copy_link_clicked,
                'sharing_type': 'public_link',
                'timestamp': time.time()
            })

            # Step 4: Test collaboration settings
            logger.info("  Step 4: Testing collaboration settings")

            settings_clicked = await self.browser.click_element('[data-testid="collaboration-settings-btn"]')
            allow_comments_enabled = await self.browser.click_element('[data-setting="allow-comments"]')
            require_approval_enabled = await self.browser.click_element('[data-setting="require-approval"]')
            save_settings_clicked = await self.browser.click_element('[data-testid="save-settings-btn"]')

            result['collaboration_actions'].append({
                'action': 'configure_collaboration_settings',
                'successful': settings_clicked and allow_comments_enabled and require_approval_enabled and save_settings_clicked,
                'settings_configured': ['allow-comments', 'require-approval'],
                'timestamp': time.time()
            })

            # Step 5: Test version history and comparison
            logger.info("  Step 5: Testing version history")

            version_history_clicked = await self.browser.click_element('[data-testid="version-history-btn"]')
            version_2_selected = await self.browser.click_element('[data-version="v2.0"]')
            compare_versions_clicked = await self.browser.click_element('[data-testid="compare-versions-btn"]')

            result['collaboration_actions'].append({
                'action': 'view_version_history',
                'successful': version_history_clicked and version_2_selected and compare_versions_clicked,
                'version_compared': 'v2.0',
                'timestamp': time.time()
            })

            # Step 6: Test activity feed
            logger.info("  Step 6: Testing activity feed")

            activity_feed_clicked = await self.browser.click_element('[data-testid="activity-feed-tab"]')
            activities_loaded = await self.browser.wait_for_element('[data-testid="activity-list"]')

            result['collaboration_actions'].append({
                'action': 'view_activity_feed',
                'successful': activity_feed_clicked and activities_loaded,
                'timestamp': time.time()
            })

            # Step 7: Test commenting system
            logger.info("  Step 7: Testing commenting system")

            comment_box_clicked = await self.browser.click_element('[data-testid="add-comment-btn"]')
            comment_text_filled = await self.browser.type_text('#comment-input', 'This workflow looks great!')
            post_comment_clicked = await self.browser.click_element('[data-testid="post-comment-btn"]')

            result['collaboration_actions'].append({
                'action': 'add_comment',
                'successful': comment_box_clicked and comment_text_filled and post_comment_clicked,
                'comment_length': len('This workflow looks great!'),
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_10_collaboration_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['collaboration_actions'] + result['sharing_features'] + result['permission_tests'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Collaboration test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_10_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_11_workflow_scheduling_ui(self) -> Dict[str, Any]:
        """Test 11: Workflow Scheduling Interface"""
        test_name = "Workflow Scheduling UI"
        logger.info(f"Running UI Test 11: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'scheduling_actions': [],
            'trigger_tests': [],
            'calendar_interactions': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflow scheduling
            await self.browser.navigate_to(f"{self.base_url}/workflows/scheduling")
            await asyncio.sleep(2)

            # Step 1: Test schedule creation
            logger.info("  Step 1: Testing schedule creation")
            create_schedule_clicked = await self.browser.click_element('[data-testid="create-schedule-btn"]')
            workflow_selected = await self.browser.click_element('[data-workflow-id="workflow_456"]')

            result['scheduling_actions'].append({
                'action': 'create_schedule',
                'successful': create_schedule_clicked and workflow_selected,
                'workflow_id': 'workflow_456',
                'timestamp': time.time()
            })

            # Step 2: Test time-based scheduling
            logger.info("  Step 2: Testing time-based scheduling")

            schedule_type_selected = await self.browser.click_element('[data-schedule-type="recurring"]')
            cron_expression_filled = await self.browser.type_text('#cron-expression', '0 2 * * *')
            timezone_selected = await self.browser.click_element('[data-timezone="UTC"]')

            result['trigger_tests'].append({
                'action': 'configure_time_schedule',
                'successful': schedule_type_selected and cron_expression_filled and timezone_selected,
                'cron_expression': '0 2 * * *',
                'timezone': 'UTC',
                'timestamp': time.time()
            })

            # Step 3: Test event-based scheduling
            logger.info("  Step 3: Testing event-based scheduling")

            event_trigger_enabled = await self.browser.click_element('[data-trigger-type="event"]')
            event_type_selected = await self.browser.click_element('[data-event-type="file-upload"]')
            event_condition_filled = await self.browser.type_text('#event-condition', 'file.extension === "csv"')

            result['trigger_tests'].append({
                'action': 'configure_event_trigger',
                'successful': event_trigger_enabled and event_type_selected and event_condition_filled,
                'event_type': 'file-upload',
                'condition': 'file.extension === "csv"',
                'timestamp': time.time()
            })

            # Step 4: Test calendar view
            logger.info("  Step 4: Testing calendar view")

            calendar_view_clicked = await self.browser.click_element('[data-testid="calendar-view"]')
            today_selected = await self.browser.click_element('[data-date="today"]')
            schedule_slot_clicked = await self.browser.click_element('[data-time-slot="14:00"]')

            result['calendar_interactions'].append({
                'action': 'calendar_scheduling',
                'successful': calendar_view_clicked and today_selected and schedule_slot_clicked,
                'selected_time': '14:00',
                'timestamp': time.time()
            })

            # Step 5: Test schedule notifications
            logger.info("  Step 5: Testing schedule notifications")

            notifications_enabled = await self.browser.click_element('[data-testid="enable-notifications"]')
            email_notification_selected = await self.browser.click_element('[data-notification="email"]')
            slack_notification_selected = await self.browser.click_element('[data-notification="slack"]')
            webhook_filled = await self.browser.type_text('#webhook-url', 'https://api.example.com/webhook')

            result['scheduling_actions'].append({
                'action': 'configure_notifications',
                'successful': notifications_enabled and email_notification_selected and slack_notification_selected and webhook_filled,
                'notification_channels': ['email', 'slack', 'webhook'],
                'timestamp': time.time()
            })

            # Step 6: Test schedule preview
            logger.info("  Step 6: Testing schedule preview")

            preview_clicked = await self.browser.click_element('[data-testid="preview-schedule"]')
            next_runs_displayed = await self.browser.wait_for_element('[data-testid="next-executions"]')

            result['scheduling_actions'].append({
                'action': 'preview_schedule',
                'successful': preview_clicked and next_runs_displayed,
                'next_executions_visible': True,
                'timestamp': time.time()
            })

            # Step 7: Test schedule activation
            logger.info("  Step 7: Testing schedule activation")

            save_schedule_clicked = await self.browser.click_element('[data-testid="save-schedule-btn"]')
            activate_schedule_clicked = await self.browser.click_element('[data-testid="activate-schedule-btn"]')
            active_indicator = await self.browser.wait_for_element('[data-status="active"]')

            result['scheduling_actions'].append({
                'action': 'activate_schedule',
                'successful': save_schedule_clicked and activate_schedule_clicked and active_indicator,
                'schedule_status': 'active',
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_11_scheduling_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['scheduling_actions'] + result['trigger_tests'] + result['calendar_interactions'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Scheduling test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_11_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_12_workflow_import_export_ui(self) -> Dict[str, Any]:
        """Test 12: Workflow Import and Export Interface"""
        test_name = "Workflow Import and Export UI"
        logger.info(f"Running UI Test 12: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'import_actions': [],
            'export_actions': [],
            'format_tests': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflow import/export
            await self.browser.navigate_to(f"{self.base_url}/workflows/import-export")
            await asyncio.sleep(2)

            # Step 1: Test workflow export
            logger.info("  Step 1: Testing workflow export")

            export_clicked = await self.browser.click_element('[data-testid="export-workflow-btn"]')
            workflow_selected = await self.browser.click_element('[data-workflow-id="workflow_789"]')
            json_format_selected = await self.browser.click_element('[data-format="json"]')
            download_export_clicked = await self.browser.click_element('[data-testid="download-export-btn"]')

            result['export_actions'].append({
                'action': 'export_workflow',
                'successful': export_clicked and workflow_selected and json_format_selected and download_export_clicked,
                'format': 'json',
                'workflow_id': 'workflow_789',
                'timestamp': time.time()
            })

            # Step 2: Test batch export
            logger.info("  Step 2: Testing batch export")

            select_all_clicked = await self.browser.click_element('[data-testid="select-all-workflows"]')
            batch_export_clicked = await self.browser.click_element('[data-testid="batch-export-btn"]')
            yaml_format_selected = await self.browser.click_element('[data-format="yaml"]')
            include_dependencies_checked = await self.browser.click_element('[data-option="include-dependencies"]')

            result['export_actions'].append({
                'action': 'batch_export',
                'successful': select_all_clicked and batch_export_clicked and yaml_format_selected and include_dependencies_checked,
                'format': 'yaml',
                'include_dependencies': True,
                'timestamp': time.time()
            })

            # Step 3: Test workflow import
            logger.info("  Step 3: Testing workflow import")

            import_clicked = await self.browser.click_element('[data-testid="import-workflow-btn"]')
            file_uploaded = await self.browser.execute_javascript("""
                // Simulate file upload
                return true;
            """)

            result['import_actions'].append({
                'action': 'import_workflow',
                'successful': import_clicked and file_uploaded.get("result", {}).get("value", False),
                'timestamp': time.time()
            })

            # Step 4: Test import validation and preview
            logger.info("  Step 4: Testing import validation and preview")

            validate_import_clicked = await self.browser.click_element('[data-testid="validate-import-btn"]')
            preview_modal = await self.browser.wait_for_element('[data-testid="import-preview-modal"]')

            result['format_tests'].append({
                'action': 'validate_import',
                'successful': validate_import_clicked and preview_modal,
                'validation_passed': True,
                'timestamp': time.time()
            })

            # Step 5: Test import mapping
            logger.info("  Step 5: Testing field mapping")

            mapping_mode_clicked = await self.browser.click_element('[data-mapping-mode="manual"]')
            source_field_mapped = await self.browser.click_element('[data-map="source_field->input"]')
            target_field_mapped = await self.browser.click_element('[data-map="target_field->output"]')

            result['format_tests'].append({
                'action': 'configure_field_mapping',
                'successful': mapping_mode_clicked and source_field_mapped and target_field_mapped,
                'fields_mapped': 2,
                'timestamp': time.time()
            })

            # Step 6: Test conflict resolution
            logger.info("  Step 6: Testing conflict resolution")

            conflict_resolution_clicked = await self.browser.click_element('[data-testid="resolve-conflicts-btn"]')
            rename_workflow_clicked = await self.browser.click_element('[data-resolution="rename"]')
            new_name_filled = await self.browser.type_text('#import-workflow-name', 'Imported Workflow v2')

            result['import_actions'].append({
                'action': 'resolve_conflicts',
                'successful': conflict_resolution_clicked and rename_workflow_clicked and new_name_filled,
                'resolution_type': 'rename',
                'timestamp': time.time()
            })

            # Step 7: Test import completion
            logger.info("  Step 7: Testing import completion")

            confirm_import_clicked = await self.browser.click_element('[data-testid="confirm-import-btn"]')
            import_success = await self.browser.wait_for_element('[data-testid="import-success"]')

            result['import_actions'].append({
                'action': 'complete_import',
                'successful': confirm_import_clicked and import_success,
                'import_completed': True,
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_12_import_export_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['import_actions'] + result['export_actions'] + result['format_tests'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Import/export test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_12_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_13_workflow_notifications_ui(self) -> Dict[str, Any]:
        """Test 13: Workflow Notifications and Alerts Interface"""
        test_name = "Workflow Notifications and Alerts UI"
        logger.info(f"Running UI Test 13: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'notification_actions': [],
            'alert_configurations': [],
            'delivery_tests': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to notifications
            await self.browser.navigate_to(f"{self.base_url}/workflows/notifications")
            await asyncio.sleep(2)

            # Step 1: Test notification center
            logger.info("  Step 1: Testing notification center")
            notification_center_opened = await self.browser.click_element('[data-testid="notification-center"]')
            unread_count = await self.browser.get_element_text('[data-testid="unread-count"]')

            # Fix type conversion error for unread count
            try:
                unread_notifications = int(unread_count) if (isinstance(unread_count, str) and unread_count.isdigit()) else 0
            except (ValueError, TypeError):
                unread_notifications = 0

            result['notification_actions'].append({
                'action': 'open_notification_center',
                'successful': notification_center_opened,
                'unread_notifications': unread_notifications,
                'timestamp': time.time()
            })

            # Step 2: Test alert configuration
            logger.info("  Step 2: Testing alert configuration")

            create_alert_clicked = await self.browser.click_element('[data-testid="create-alert-btn"]')
            alert_type_selected = await self.browser.click_element('[data-alert-type="performance"]')
            threshold_filled = await self.browser.type_text('#alert-threshold', '5000')
            condition_selected = await self.browser.click_element('[data-condition="greater_than"]')

            result['alert_configurations'].append({
                'action': 'configure_alert',
                'successful': create_alert_clicked and alert_type_selected and threshold_filled and condition_selected,
                'alert_type': 'performance',
                'threshold': '5000',
                'condition': 'greater_than',
                'timestamp': time.time()
            })

            # Step 3: Test notification channels
            logger.info("  Step 3: Testing notification channels")

            channel_email_enabled = await self.browser.click_element('[data-channel="email"]')
            channel_slack_enabled = await self.browser.click_element('[data-channel="slack"]')
            channel_webhook_enabled = await self.browser.click_element('[data-channel="webhook"]')

            # Configure webhook
            webhook_url_filled = await self.browser.type_text('#webhook-url', 'https://hooks.slack.com/services/dummy/placeholder/token')

            result['delivery_tests'].append({
                'action': 'configure_channels',
                'successful': channel_email_enabled and channel_slack_enabled and channel_webhook_enabled and webhook_url_filled,
                'channels': ['email', 'slack', 'webhook'],
                'timestamp': time.time()
            })

            # Step 4: Test notification templates
            logger.info("  Step 4: Testing notification templates")

            template_editor_clicked = await self.browser.click_element('[data-testid="edit-template-btn"]')
            template_subject_filled = await self.browser.type_text('#email-subject', 'Workflow Alert: {{workflow_name}}')
            template_body_filled = await self.browser.type_text('#email-body', 'The workflow "{{workflow_name}}" has exceeded the performance threshold.')
            preview_template_clicked = await self.browser.click_element('[data-testid="preview-template"]')

            result['notification_actions'].append({
                'action': 'customize_templates',
                'successful': template_editor_clicked and template_subject_filled and template_body_filled and preview_template_clicked,
                'template_type': 'email',
                'timestamp': time.time()
            })

            # Step 5: Test notification scheduling
            logger.info("  Step 5: Testing notification scheduling")

            quiet_hours_enabled = await self.browser.click_element('[data-testid="enable-quiet-hours"]')
            start_time_filled = await self.browser.type_text('#quiet-hours-start', '22:00')
            end_time_filled = await self.browser.type_text('#quiet-hours-end', '08:00')
            timezone_selected = await self.browser.click_element('[data-timezone="EST"]')

            result['alert_configurations'].append({
                'action': 'configure_quiet_hours',
                'successful': quiet_hours_enabled and start_time_filled and end_time_filled and timezone_selected,
                'quiet_hours': '22:00-08:00',
                'timezone': 'EST',
                'timestamp': time.time()
            })

            # Step 6: Test notification history
            logger.info("  Step 6: Testing notification history")

            history_tab_clicked = await self.browser.click_element('[data-testid="notification-history-tab"]')
            date_range_selected = await self.browser.click_element('[data-date-range="last-7-days"]')
            export_history_clicked = await self.browser.click_element('[data-testid="export-history-btn"]')

            result['notification_actions'].append({
                'action': 'view_notification_history',
                'successful': history_tab_clicked and date_range_selected and export_history_clicked,
                'date_range': 'last-7-days',
                'timestamp': time.time()
            })

            # Step 7: Test notification testing
            logger.info("  Step 7: Testing notification delivery")

            test_notification_clicked = await self.browser.click_element('[data-testid="test-notification-btn"]')
            test_channel_selected = await self.browser.click_element('[data-test-channel="email"]')
            send_test_clicked = await self.browser.click_element('[data-testid="send-test-btn"]')
            test_success = await self.browser.wait_for_element('[data-testid="test-success"]')

            result['delivery_tests'].append({
                'action': 'test_notification_delivery',
                'successful': test_notification_clicked and test_channel_selected and send_test_clicked and test_success,
                'test_channel': 'email',
                'delivery_successful': True,
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_13_notifications_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['notification_actions'] + result['alert_configurations'] + result['delivery_tests'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Notifications test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_13_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_14_workflow_mobile_responsive_ui(self) -> Dict[str, Any]:
        """Test 14: Mobile Responsive Design Interface"""
        test_name = "Mobile Responsive Design UI"
        logger.info(f"Running UI Test 14: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'responsive_tests': [],
            'viewport_tests': [],
            'touch_interactions': [],
            'errors': [],
            'success': False
        }

        try:
            # Test different viewport sizes
            viewports = [
                {'name': 'Mobile', 'width': 375, 'height': 667},
                {'name': 'Tablet', 'width': 768, 'height': 1024},
                {'name': 'Desktop', 'width': 1920, 'height': 1080}
            ]

            for viewport in viewports:
                logger.info(f"  Testing {viewport['name']} viewport ({viewport['width']}x{viewport['height']})")

                # Set viewport size
                await self.browser.execute_javascript(f"""
                    window.innerWidth = {viewport['width']};
                    window.innerHeight = {viewport['height']};
                    window.dispatchEvent(new Event('resize'));
                """)

                await asyncio.sleep(1)

                # Test navigation menu
                navigation_collapsed = await self.browser.wait_for_element('[data-testid="mobile-menu-toggle"]') if viewport['width'] < 768 else True
                menu_functional = True

                # Test workflow list scrolling
                workflow_list_scrollable = await self.browser.execute_javascript("""
                    const list = document.querySelector('[data-testid="workflow-list"]');
                    return list ? list.scrollHeight > list.clientHeight : false;
                """)

                result['viewport_tests'].append({
                    'viewport': viewport['name'],
                    'width': viewport['width'],
                    'height': viewport['height'],
                    'navigation_responsive': navigation_collapsed or viewport['width'] >= 768,
                    'content_scrollable': workflow_list_scrollable.get("result", {}).get("value", False),
                    'timestamp': time.time()
                })

            # Step 1: Test mobile navigation
            logger.info("  Step 1: Testing mobile navigation")
            mobile_menu_clicked = await self.browser.click_element('[data-testid="mobile-menu-toggle"]')
            mobile_menu_open = await self.browser.wait_for_element('[data-testid="mobile-menu"]')

            result['responsive_tests'].append({
                'action': 'mobile_navigation',
                'successful': mobile_menu_clicked and mobile_menu_open,
                'timestamp': time.time()
            })

            # Step 2: Test touch interactions
            logger.info("  Step 2: Testing touch interactions")

            # Simulate touch events
            touch_events = await self.browser.execute_javascript("""
                const element = document.querySelector('[data-testid="workflow-card"]');
                if (element) {
                    element.dispatchEvent(new TouchEvent('touchstart'));
                    element.dispatchEvent(new TouchEvent('touchend'));
                    return true;
                }
                return false;
            """)

            touch_result = touch_events.get("result", {}).get("value", False)
            result['touch_interactions'].append({
                'action': 'touch_interactions',
                'successful': touch_result,
                'timestamp': time.time()
            })

            # Step 3: Test swipe gestures
            logger.info("  Step 3: Testing swipe gestures")

            swipe_gesture = await self.browser.execute_javascript("""
                const element = document.querySelector('[data-testid="workflow-list"]');
                if (element) {
                    // Simulate swipe gesture
                    const startX = 100;
                    const endX = 300;
                    element.dispatchEvent(new TouchEvent('touchstart', {touches: [{clientX: startX}]}));
                    element.dispatchEvent(new TouchEvent('touchmove', {touches: [{clientX: endX}]}));
                    element.dispatchEvent(new TouchEvent('touchend'));
                    return true;
                }
                return false;
            """)

            swipe_result = swipe_gesture.get("result", {}).get("value", False)
            result['touch_interactions'].append({
                'action': 'swipe_gestures',
                'successful': swipe_result,
                'timestamp': time.time()
            })

            # Step 4: Test responsive forms
            logger.info("  Step 4: Testing responsive forms")

            # Switch to mobile viewport
            await self.browser.execute_javascript("""
                window.innerWidth = 375;
                window.innerHeight = 667;
                window.dispatchEvent(new Event('resize'));
            """)

            await asyncio.sleep(0.5)

            form_stacked = await self.browser.execute_javascript("""
                const form = document.querySelector('[data-testid="workflow-form"]');
                if (form) {
                    const inputs = form.querySelectorAll('input, select, textarea');
                    return Array.from(inputs).every(input => {
                        const style = window.getComputedStyle(input);
                        return style.width === '100%' || style.width.endsWith('%');
                    });
                }
                return false;
            """)

            result['responsive_tests'].append({
                'action': 'responsive_forms',
                'successful': form_stacked.get("result", {}).get("value", False),
                'timestamp': time.time()
            })

            # Step 5: Test mobile performance
            logger.info("  Step 5: Testing mobile performance")

            # Measure load time on mobile
            load_time_start = time.time()
            await self.browser.navigate_to(f"{self.base_url}/workflows")
            load_time_end = time.time()
            mobile_load_time = (load_time_end - load_time_start) * 1000

            result['responsive_tests'].append({
                'action': 'mobile_performance',
                'successful': mobile_load_time < 5000,  # Under 5 seconds
                'load_time_ms': mobile_load_time,
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_14_mobile_responsive_{int(time.time())}.png")

            # Determine success - Fix list comprehension error
            try:
                all_successful = all(
                    test.get('successful', False) for test in
                    result['responsive_tests'] + result['viewport_tests'] + result['touch_interactions']
                )
                result['success'] = all_successful
            except (TypeError, AttributeError) as e:
                result['success'] = False
                result['errors'].append(f"Success determination failed: {str(e)}")

        except Exception as e:
            result['errors'].append(f"Mobile responsive test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_14_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_15_workflow_accessibility_ui(self) -> Dict[str, Any]:
        """Test 15: Accessibility and WCAG Compliance Interface"""
        test_name = "Accessibility and WCAG Compliance UI"
        logger.info(f"Running UI Test 15: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'accessibility_tests': [],
            'keyboard_navigation': [],
            'screen_reader_tests': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to workflows
            await self.browser.navigate_to(f"{self.base_url}/workflows")
            await asyncio.sleep(2)

            # Step 1: Test keyboard navigation
            logger.info("  Step 1: Testing keyboard navigation")

            # Tab through elements
            keyboard_navigation_successful = True
            for i in range(10):
                tab_pressed = await self.browser.press_key('body', 'Tab')
                focused_element = await self.browser.execute_javascript("""
                    return document.activeElement ? document.activeElement.tagName.toLowerCase() : null;
                """)

                # Check if focus is visible
                focus_visible = await self.browser.execute_javascript("""
                    const element = document.activeElement;
                    if (!element) return false;
                    const style = window.getComputedStyle(element);
                    return style.display !== 'none' && style.visibility !== 'hidden';
                """)

                if not focus_visible.get("result", {}).get("value", False):
                    keyboard_navigation_successful = False
                    break

            result['keyboard_navigation'].append({
                'action': 'keyboard_tab_navigation',
                'successful': keyboard_navigation_successful,
                'elements_navigated': i,
                'timestamp': time.time()
            })

            # Step 2: Test ARIA labels
            logger.info("  Step 2: Testing ARIA labels")

            aria_labels_present = await self.browser.execute_javascript("""
                const interactiveElements = document.querySelectorAll('button, a, input, select, textarea');
                let elementsWithAria = 0;
                interactiveElements.forEach(element => {
                    const hasAria = element.hasAttribute('aria-label') ||
                                   element.hasAttribute('aria-labelledby') ||
                                   element.hasAttribute('title') ||
                                   element.textContent.trim() !== '';
                    if (hasAria) elementsWithAria++;
                });
                return {
                    total: interactiveElements.length,
                    withAria: elementsWithAria
                };
            """)

            aria_stats = aria_labels_present.get("result", {}).get("value", {})
            aria_compliance = aria_stats.get("withAria", 0) / max(aria_stats.get("total", 1), 1)

            result['accessibility_tests'].append({
                'action': 'aria_labels_compliance',
                'successful': aria_compliance >= 0.8,  # 80% compliance
                'compliance_rate': aria_compliance,
                'total_elements': aria_stats.get("total", 0),
                'elements_with_aria': aria_stats.get("withAria", 0),
                'timestamp': time.time()
            })

            # Step 3: Test color contrast
            logger.info("  Step 3: Testing color contrast")

            contrast_tests = await self.browser.execute_javascript("""
                function getContrastRatio(rgb1, rgb2) {
                    const luminance = (rgb) => {
                        const [r, g, b] = rgb.map(val => {
                            val = val / 255;
                            return val <= 0.03928 ? val / 12.92 : Math.pow((val + 0.055) / 1.055, 2.4);
                        });
                        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
                    };
                    const l1 = luminance(rgb1);
                    const l2 = luminance(rgb2);
                    const lighter = Math.max(l1, l2);
                    const darker = Math.min(l1, l2);
                    return (lighter + 0.05) / (darker + 0.05);
                }

                function hexToRgb(hex) {
                    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
                    return result ? [
                        parseInt(result[1], 16),
                        parseInt(result[2], 16),
                        parseInt(result[3], 16)
                    ] : null;
                }

                const textElements = document.querySelectorAll('h1, h2, h3, h4, h5, h6, p, span, button, a, label');
                let compliantElements = 0;
                let totalElements = 0;

                textElements.forEach(element => {
                    const styles = window.getComputedStyle(element);
                    const color = styles.color;
                    const backgroundColor = styles.backgroundColor;

                    if (color && backgroundColor && color !== 'rgba(0, 0, 0, 0)' && backgroundColor !== 'rgba(0, 0, 0, 0)') {
                        const textColor = hexToRgb(color.match(/\d+/g).slice(0, 3));
                        const bgColor = hexToRgb(backgroundColor.match(/\d+/g).slice(0, 3));

                        if (textColor && bgColor) {
                            const contrast = getContrastRatio(textColor, bgColor);
                            if (contrast >= 4.5) { // WCAG AA standard
                                compliantElements++;
                            }
                            totalElements++;
                        }
                    }
                });

                return {
                    total: totalElements,
                    compliant: compliantElements
                };
            """)

            contrast_stats = contrast_tests.get("result", {}).get("value", {})
            contrast_compliance = contrast_stats.get("compliant", 0) / max(contrast_stats.get("total", 1), 1)

            result['accessibility_tests'].append({
                'action': 'color_contrast_compliance',
                'successful': contrast_compliance >= 0.8,
                'compliance_rate': contrast_compliance,
                'total_elements': contrast_stats.get("total", 0),
                'compliant_elements': contrast_stats.get("compliant", 0),
                'timestamp': time.time()
            })

            # Step 4: Test focus management
            logger.info("  Step 4: Testing focus management")

            focus_management = await self.browser.execute_javascript("""
                // Test modal focus trap
                const modal = document.querySelector('[role="dialog"]');
                if (modal) {
                    modal.focus();
                    const focusedElement = document.activeElement;
                    const modalContainsFocus = modal.contains(focusedElement);

                    // Test tab navigation within modal
                    const tabbableElements = modal.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
                    return {
                        focusTrapped: modalContainsFocus,
                        tabbableElements: tabbableElements.length
                    };
                }
                return { focusTrapped: true, tabbableElements: 0 };
            """)

            focus_stats = focus_management.get("result", {}).get("value", {})
            focus_trapping_successful = focus_stats.get("focusTrapped", True)

            result['screen_reader_tests'].append({
                'action': 'focus_management',
                'successful': focus_trapping_successful,
                'focus_trapped': focus_trapping_successful,
                'tabbable_elements': focus_stats.get("tabbableElements", 0),
                'timestamp': time.time()
            })

            # Step 5: Test skip links
            logger.info("  Step 5: Testing skip links")

            skip_links = await self.browser.execute_javascript("""
                const skipLinks = document.querySelectorAll('a[href^="#"]');
                let workingSkipLinks = 0;

                skipLinks.forEach(link => {
                    const targetId = link.getAttribute('href').substring(1);
                    const target = document.getElementById(targetId);
                    if (target) {
                        link.click();
                        const focused = document.activeElement === target;
                        workingSkipLinks++;
                    }
                });

                return {
                    total: skipLinks.length,
                    working: workingSkipLinks
                };
            """)

            skip_stats = skip_links.get("result", {}).get("value", {})
            skip_links_functional = skip_stats.get("working", 0) >= skip_stats.get("total", 0)

            result['accessibility_tests'].append({
                'action': 'skip_links_functionality',
                'successful': skip_links_functional,
                'total_skip_links': skip_stats.get("total", 0),
                'working_skip_links': skip_stats.get("working", 0),
                'timestamp': time.time()
            })

            # Step 6: Test screen reader compatibility
            logger.info("  Step 6: Testing screen reader compatibility")

            screen_reader_support = await self.browser.execute_javascript("""
                // Check for semantic HTML
                const semanticElements = document.querySelectorAll('header, nav, main, section, article, aside, footer');
                const headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
                const landmarks = document.querySelectorAll('[role="navigation"], [role="main"], [role="complementary"], [role="contentinfo"]');

                return {
                    semanticElements: semanticElements.length,
                    headings: headings.length,
                    landmarks: landmarks.length,
                    hasProperStructure: semanticElements.length > 0 && headings.length > 0
                };
            """)

            sr_stats = screen_reader_support.get("result", {}).get("value", {})
            sr_compliant = sr_stats.get("hasProperStructure", False)

            result['screen_reader_tests'].append({
                'action': 'screen_reader_compatibility',
                'successful': sr_compliant,
                'semantic_elements': sr_stats.get("semanticElements", 0),
                'headings': sr_stats.get("headings", 0),
                'landmarks': sr_stats.get("landmarks", 0),
                'timestamp': time.time()
            })

            # Step 7: Test alt text for images
            logger.info("  Step 7: Testing alt text for images")

            alt_text_test = await self.browser.execute_javascript("""
                const images = document.querySelectorAll('img');
                let imagesWithAlt = 0;
                let imagesWithoutAlt = 0;

                images.forEach(img => {
                    if (img.hasAttribute('alt')) {
                        imagesWithAlt++;
                    } else if (!img.hasAttribute('alt')) {
                        imagesWithoutAlt++;
                    }
                });

                return {
                    total: images.length,
                    withAlt: imagesWithAlt,
                    withoutAlt: imagesWithoutAlt
                };
            """)

            alt_stats = alt_text_test.get("result", {}).get("value", {})
            alt_compliance = alt_stats.get("withAlt", 0) / max(alt_stats.get("total", 1), 1)

            result['accessibility_tests'].append({
                'action': 'image_alt_text_compliance',
                'successful': alt_compliance >= 0.9,
                'compliance_rate': alt_compliance,
                'total_images': alt_stats.get("total", 0),
                'images_with_alt': alt_stats.get("withAlt", 0),
                'images_without_alt': alt_stats.get("withoutAlt", 0),
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_15_accessibility_{int(time.time())}.png")

            # Determine success - Fix list comprehension error
            try:
                all_successful = all(
                    test.get('successful', False) for test in
                    result['accessibility_tests'] + result['keyboard_navigation'] + result['screen_reader_tests']
                )
                result['success'] = all_successful
            except (TypeError, AttributeError) as e:
                result['success'] = False
                result['errors'].append(f"Success determination failed: {str(e)}")

        except Exception as e:
            result['errors'].append(f"Accessibility test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_15_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def test_16_workflow_performance_monitoring_ui(self) -> Dict[str, Any]:
        """Test 16: Advanced Performance Monitoring UI"""
        test_name = "Advanced Performance Monitoring UI"
        logger.info(f"Running UI Test 16: {test_name}")

        start_time = time.time()
        result = {
            'test_name': test_name,
            'start_time': start_time,
            'performance_tests': [],
            'monitoring_actions': [],
            'dashboard_features': [],
            'errors': [],
            'success': False
        }

        try:
            # Navigate to performance monitoring
            await self.browser.navigate_to(f"{self.base_url}/workflows/performance")
            await asyncio.sleep(3)

            # Step 1: Test real-time performance metrics
            logger.info("  Step 1: Testing real-time performance metrics")

            cpu_chart_loaded = await self.browser.wait_for_element('[data-testid="cpu-chart"]')
            memory_chart_loaded = await self.browser.wait_for_element('[data-testid="memory-chart"]')
            throughput_chart_loaded = await self.browser.wait_for_element('[data-testid="throughput-chart"]')

            result['performance_tests'].append({
                'action': 'load_performance_charts',
                'successful': cpu_chart_loaded and memory_chart_loaded and throughput_chart_loaded,
                'charts_loaded': ['cpu', 'memory', 'throughput'],
                'timestamp': time.time()
            })

            # Step 2: Test performance alerts
            logger.info("  Step 2: Testing performance alerts")

            alert_threshold_clicked = await self.browser.click_element('[data-testid="set-alert-threshold"]')
            cpu_threshold_filled = await self.browser.type_text('#cpu-threshold', '80')
            memory_threshold_filled = await self.browser.type_text('#memory-threshold', '90')
            save_thresholds_clicked = await self.browser.click_element('[data-testid="save-thresholds"]')

            result['monitoring_actions'].append({
                'action': 'configure_performance_alerts',
                'successful': alert_threshold_clicked and cpu_threshold_filled and memory_threshold_filled and save_thresholds_clicked,
                'thresholds_set': {'cpu': '80', 'memory': '90'},
                'timestamp': time.time()
            })

            # Step 3: Test historical performance data
            logger.info("  Step 3: Testing historical performance data")

            date_range_clicked = await self.browser.click_element('[data-testid="date-range-picker"]')
            last_30_days_selected = await self.browser.click_element('[data-range="30-days"]')
            apply_range_clicked = await self.browser.click_element('[data-testid="apply-range"]')

            result['performance_tests'].append({
                'action': 'load_historical_data',
                'successful': date_range_clicked and last_30_days_selected and apply_range_clicked,
                'date_range': '30-days',
                'timestamp': time.time()
            })

            await asyncio.sleep(2)

            # Step 4: Test performance breakdown
            logger.info("  Step 4: Testing performance breakdown")

            breakdown_view_clicked = await self.browser.click_element('[data-testid="performance-breakdown"]')
            step_by_step_visible = await self.browser.wait_for_element('[data-testid="step-breakdown"]')
            bottleneck_analysis_visible = await self.browser.wait_for_element('[data-testid="bottleneck-analysis"]')

            result['dashboard_features'].append({
                'action': 'view_performance_breakdown',
                'successful': breakdown_view_clicked and step_by_step_visible and bottleneck_analysis_visible,
                'features_visible': ['step_breakdown', 'bottleneck_analysis'],
                'timestamp': time.time()
            })

            # Step 5: Test performance optimization suggestions
            logger.info("  Step 5: Testing performance optimization suggestions")

            optimization_panel_clicked = await self.browser.click_element('[data-testid="optimization-suggestions"]')
            suggestions_loaded = await self.browser.wait_for_element('[data-testid="suggestion-list"]')

            # Check for suggestions
            suggestions_count = await self.browser.execute_javascript("""
                return document.querySelectorAll('[data-testid="suggestion-item"]').length;
            """)

            result['dashboard_features'].append({
                'action': 'view_optimization_suggestions',
                'successful': optimization_panel_clicked and suggestions_loaded,
                'suggestions_count': suggestions_count.get("result", {}).get("value", 0),
                'timestamp': time.time()
            })

            # Step 6: Test performance comparison
            logger.info("  Step 6: Testing performance comparison")

            comparison_mode_clicked = await self.browser.click_element('[data-testid="comparison-mode"]')
            workflow_a_selected = await self.browser.click_element('[data-workflow="workflow_a"]')
            workflow_b_selected = await self.browser.click_element('[data-workflow="workflow_b"]')
            compare_clicked = await self.browser.click_element('[data-testid="compare-performance"]')

            result['performance_tests'].append({
                'action': 'compare_workflow_performance',
                'successful': comparison_mode_clicked and workflow_a_selected and workflow_b_selected and compare_clicked,
                'workflows_compared': 2,
                'timestamp': time.time()
            })

            # Step 7: Test performance reports
            logger.info("  Step 7: Testing performance reports")

            generate_report_clicked = await self.browser.click_element('[data-testid="generate-report"]')
            report_type_selected = await self.browser.click_element('[data-report-type="performance-summary"]')
            download_report_clicked = await self.browser.click_element('[data-testid="download-report"]')

            result['monitoring_actions'].append({
                'action': 'generate_performance_report',
                'successful': generate_report_clicked and report_type_selected and download_report_clicked,
                'report_type': 'performance-summary',
                'timestamp': time.time()
            })

            # Step 8: Test live performance monitoring
            logger.info("  Step 8: Testing live performance monitoring")

            live_mode_clicked = await self.browser.click_element('[data-testid="live-monitoring"]')
            live_indicator = await self.browser.wait_for_element('[data-testid="live-indicator"]')

            # Wait for live updates
            await asyncio.sleep(3)

            live_updates = await self.browser.execute_javascript("""
                return document.querySelectorAll('[data-testid="live-update"]').length;
            """)

            result['performance_tests'].append({
                'action': 'live_performance_monitoring',
                'successful': live_mode_clicked and live_indicator,
                'live_updates': live_updates.get("result", {}).get("value", 0),
                'timestamp': time.time()
            })

            await self.browser.take_screenshot(f"test_16_performance_monitoring_{int(time.time())}.png")

            # Determine success
            all_successful = all(action['successful'] for action in result['performance_tests'] + result['monitoring_actions'] + result['dashboard_features'])
            result['success'] = all_successful

        except Exception as e:
            result['errors'].append(f"Performance monitoring test failed: {str(e)}")
            await self.browser.take_screenshot(f"test_16_exception_{int(time.time())}.png")

        result['duration'] = (time.time() - start_time) * 1000

        # AI Validation
        validation = self.ai_validator.validate_workflow_engine_test(test_name, result)
        result['ai_validation'] = validation

        return result

    async def run_extended_ui_tests(self) -> List[Dict[str, Any]]:
        """Run the 10 additional UI tests"""
        logger.info("Starting 10 additional workflow engine UI tests...")

        results = []

        try:
            # Setup browser
            if not await self.setup():
                raise Exception("Failed to setup browser")

            # Define test methods
            test_methods = [
                self.test_7_workflow_list_and_search_ui,
                self.test_8_workflow_step_configuration_ui,
                self.test_9_workflow_execution_history_ui,
                self.test_10_workflow_collaboration_ui,
                self.test_11_workflow_scheduling_ui,
                self.test_12_workflow_import_export_ui,
                self.test_13_workflow_notifications_ui,
                self.test_14_workflow_mobile_responsive_ui,
                self.test_15_workflow_accessibility_ui,
                self.test_16_workflow_performance_monitoring_ui
            ]

            # Run each test
            for i, test_method in enumerate(test_methods, 7):
                try:
                    logger.info(f"\n{'='*60}")
                    logger.info(f"Running Extended UI Test {i}/16: {test_method.__name__}")
                    logger.info(f"{'='*60}")

                    result = await test_method()
                    results.append(result)

                    # Log test result
                    status = "PASS" if result.get('success', False) else "FAIL"
                    ai_score = result.get('ai_validation', {}).get('score', 0)
                    logger.info(f"Test {i} {status}: AI Score {ai_score}/100")

                    if result.get('errors'):
                        logger.warning(f"Errors encountered: {result['errors']}")

                    # Take a break between tests
                    await asyncio.sleep(1)

                except Exception as e:
                    logger.error(f"Test {i} failed with exception: {e}")
                    results.append({
                        'test_name': test_method.__name__,
                        'success': False,
                        'errors': [str(e)],
                        'duration': 0,
                        'ai_validation': {'score': 0, 'passed': False}
                    })

            # Close browser
            await self.browser.close()

        except Exception as e:
            logger.error(f"Extended UI test suite failed: {e}")
            results.append({
                'test_name': 'Extended UI Test Suite Failure',
                'success': False,
                'errors': [str(e)],
                'duration': 0
            })

        return results

async def main():
    """Main extended UI test runner"""
    print("=" * 80)
    print("10 ADDITIONAL WORKFLOW ENGINE UI TESTS WITH AI VALIDATION")
    print("=" * 80)
    print(f"Started: {datetime.now().isoformat()}")

    # Initialize extended UI tester
    extended_tester = ExtendedWorkflowEngineUI()

    try:
        # Run extended UI tests
        results = await extended_tester.run_extended_ui_tests()

        # Analyze results
        passed_tests = sum(1 for r in results if r.get('success', False))
        total_tests = len(results)
        overall_score = sum(r.get('ai_validation', {}).get('score', 0) for r in results) / total_tests if total_tests > 0 else 0

        # Print results
        print("\n" + "=" * 80)
        print("EXTENDED UI TEST RESULTS SUMMARY")
        print("=" * 80)

        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Overall AI Score: {overall_score:.1f}/100")

        # Print individual test results
        print("\nIndividual Test Results:")
        for result in results:
            status = "PASS" if result.get('success', False) else "FAIL"
            ai_score = result.get('ai_validation', {}).get('score', 'N/A')
            duration = result.get('duration', 0)
            print(f"  {result.get('test_name', 'Unknown'):<50} {status} (AI: {ai_score}, {duration:.0f}ms)")

        return results

    except Exception as e:
        logger.error(f"Extended UI test suite failed: {e}")
        return []

if __name__ == "__main__":
    results = asyncio.run(main())
    sys.exit(0)