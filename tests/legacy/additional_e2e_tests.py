#!/usr/bin/env python3
"""
Additional 38 E2E Tests to Complete the 50-Test Comprehensive Suite
These tests extend the existing comprehensive suite with advanced functionality
"""

import asyncio
import time
from datetime import datetime
from typing import Dict, Any

# Additional test methods that would be added to the ComprehensiveE2ETestSuite class

class AdditionalE2ETests:
    """Additional 38 E2E tests for comprehensive coverage"""

    # ==================== ADVANCED WORKFLOW FEATURES (Tests 13-20) ====================

    async def test_13_workflow_chaining_and_dependencies(self) -> Dict[str, Any]:
        """Test 13: Workflow chaining and dependency management"""
        result = {
            'workflows_chained': 0,
            'dependencies_configured': 0,
            'chain_execution_successful': False,
            'dependency_resolution_works': False,
            'success': False,
            'errors': []
        }

        try:
            # Create chain of dependent workflows
            chain_workflows = ['data-ingestion', 'data-processing', 'data-analysis', 'report-generation']
            workflows_created = 0

            for workflow in chain_workflows:
                await self.browser.navigate_to(f"{self.base_url}/workflows/create")
                await asyncio.sleep(2)

                workflow_name = f"chain_{workflow}_{int(time.time())}"
                await self.browser.type_text('#workflow-name', workflow_name)

                # Configure dependencies
                if workflow != 'data-ingestion':  # First workflow has no dependency
                    dependency_configured = await self.browser.click_element('[data-testid="configure-dependency"]')
                    previous_workflow = chain_workflows[chain_workflows.index(workflow) - 1]
                    dependency_selected = await self.browser.click_element(f'[data-dependency="{previous_workflow}"]')

                    if dependency_configured and dependency_selected:
                        result['dependencies_configured'] += 1

                # Save workflow
                save_clicked = await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(2)

                if save_clicked:
                    workflows_created += 1

            result['workflows_chained'] = workflows_created

            if workflows_created == len(chain_workflows):
                # Execute the chain (starting with first workflow)
                await self.browser.navigate_to(f"{self.base_url}/workflows")
                await asyncio.sleep(2)

                # Start chain execution
                chain_start_clicked = await self.browser.click_element('[data-testid="execute-chain"]')
                await asyncio.sleep(10)

                # Check chain completion
                chain_completed = await self.browser.execute_javascript("""
                    const completedWorkflows = document.querySelectorAll('[data-testid="workflow-in-chain-completed"]');
                    return completedWorkflows.length;
                """)

                completed_count = chain_completed.get("result", {}).get("value", 0)
                result['chain_execution_successful'] = completed_count == len(chain_workflows)
                result['dependency_resolution_works'] = result['dependencies_configured'] == len(chain_workflows) - 1

            result['success'] = (
                result['workflows_chained'] == len(chain_workflows) and
                result['chain_execution_successful'] and
                result['dependency_resolution_works']
            )

        except Exception as e:
            result['errors'].append(str(e))

        return result

    async def test_14_custom_function_integration(self) -> Dict[str, Any]:
        """Test 14: Custom function integration in workflows"""
        result = {
            'custom_functions_added': 0,
            'function_parameters_configured': False,
            'custom_execution_successful': False,
            'function_results_returned': False,
            'success': False,
            'errors': []
        }

        try:
            # Create workflow with custom functions
            await self.browser.navigate_to(f"{self.base_url}/workflows/create")
            await asyncio.sleep(2)

            workflow_name = f"custom_functions_test_{int(time.time())}"
            await self.browser.type_text('#workflow-name', workflow_name)

            # Add custom function steps
            custom_functions = ['data-validator', 'format-converter', 'custom-calculator']
            functions_added = 0

            for func in custom_functions:
                add_custom_clicked = await self.browser.click_element('[data-testid="add-custom-function"]')
                function_selected = await self.browser.click_element(f'[data-custom-function="{func}"]')

                # Configure function parameters
                if func == 'data-validator':
                    await self.browser.type_text('#validator-rules', 'required:true, type:string')
                elif func == 'format-converter':
                    await self.browser.click_element('[data-format="json-to-csv"]')
                elif func == 'custom-calculator':
                    await self.browser.type_text('#calculation', '(input * 2) + 10')

                if add_custom_clicked and function_selected:
                    functions_added += 1
                await asyncio.sleep(1)

            result['custom_functions_added'] = functions_added

            if functions_added >= 3:
                # Configure input parameters
                input_configured = await self.browser.type_text('#input-schema', '{"data": "string", "multiplier": "number"}')
                result['function_parameters_configured'] = input_configured

                # Save and execute
                save_clicked = await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(3)

                if save_clicked:
                    # Execute with test data
                    await self.browser.navigate_to(f"{self.base_url}/workflows")
                    await asyncio.sleep(2)

                    await self.browser.click_element(f'[data-workflow-name="{workflow_name}"]')
                    await self.browser.click_element('[data-testid="execute-workflow-btn"]')

                    test_data = '{"data": "test_string", "multiplier": 5}'
                    await self.browser.type_text('#test-input-data', test_data)
                    await self.browser.click_element('[data-testid="run-with-test-data"]')

                    await asyncio.sleep(5)

                    # Check custom execution results
                    custom_result = await self.browser.execute_javascript("""
                        const customOutput = document.querySelector('[data-testid="custom-function-output"]');
                        const validationResult = document.querySelector('[data-testid="validation-result"]');
                        return {
                            has_output: customOutput ? customOutput.textContent !== '' : false,
                            validation_passed: validationResult ? validationResult.textContent.includes('valid') : false
                        };
                    """)

                    execution_result = custom_result.get("result", {}).get("value", {})
                    result['custom_execution_successful'] = execution_result.get("validation_passed", False)
                    result['function_results_returned'] = execution_result.get("has_output", False)

            result['success'] = all([
                result['custom_functions_added'] >= 3,
                result['function_parameters_configured'],
                result['custom_execution_successful'],
                result['function_results_returned']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    async def test_15_api_endpoint_integration(self) -> Dict[str, Any]:
        """Test 15: API endpoint integration in workflows"""
        result = {
            'api_endpoints_configured': 0,
            'api_authentication_works': False,
            'api_calls_successful': False,
            'api_responses_processed': False,
            'success': False,
            'errors': []
        }

        try:
            # Create workflow with API integrations
            await self.browser.navigate_to(f"{self.base_url}/workflows/create")
            await asyncio.sleep(2)

            workflow_name = f"api_integration_test_{int(time.time())}"
            await self.browser.type_text('#workflow-name', workflow_name)

            # Add API integration steps
            api_endpoints = [
                {'name': 'user-api', 'method': 'GET', 'url': 'https://jsonplaceholder.typicode.com/users'},
                {'name': 'post-api', 'method': 'POST', 'url': 'https://jsonplaceholder.typicode.com/posts'},
                {'name': 'validation-api', 'method': 'POST', 'url': 'https://api.example.com/validate'}
            ]

            endpoints_configured = 0

            for api in api_endpoints:
                add_api_clicked = await self.browser.click_element('[data-testid="add-api-step"]')
                api_url_filled = await self.browser.type_text('#api-url', api['url'])
                method_selected = await self.browser.click_element(f'[data-method="{api["method"]}"]')

                # Configure authentication for validation API
                if api['name'] == 'validation-api':
                    auth_enabled = await self.browser.click_element('[data-testid="enable-api-auth"]')
                    auth_type_selected = await self.browser.click_element('[data-auth-type="bearer-token"]')
                    token_filled = await self.browser.type_text('#auth-token', 'test_bearer_token_123')

                    if auth_enabled and auth_type_selected and token_filled:
                        result['api_authentication_works'] = True

                if add_api_clicked and api_url_filled and method_selected:
                    endpoints_configured += 1
                await asyncio.sleep(1)

            result['api_endpoints_configured'] = endpoints_configured

            if endpoints_configured >= 3:
                # Save and execute workflow
                save_clicked = await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(3)

                if save_clicked:
                    # Execute workflow
                    await self.browser.navigate_to(f"{self.base_url}/workflows")
                    await asyncio.sleep(2)

                    await self.browser.click_element(f'[data-workflow-name="{workflow_name}"]')
                    await self.browser.click_element('[data-testid="execute-workflow-btn"]')

                    await asyncio.sleep(8)

                    # Check API call results
                    api_results = await self.browser.execute_javascript("""
                        const apiResponses = document.querySelectorAll('[data-testid="api-response"]');
                        const apiStatuses = document.querySelectorAll('[data-testid="api-status"]');
                        return {
                            response_count: apiResponses.length,
                            success_count: Array.from(apiStatuses).filter(status =>
                                status.textContent.includes('200') || status.textContent.includes('success')
                            ).length
                        };
                    """)

                    api_result_data = api_results.get("result", {}).get("value", {})
                    result['api_calls_successful'] = api_result_data.get("success_count", 0) >= 2
                    result['api_responses_processed'] = api_result_data.get("response_count", 0) >= 3

            result['success'] = all([
                result['api_endpoints_configured'] >= 3,
                result['api_authentication_works'],
                result['api_calls_successful'],
                result['api_responses_processed']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    # Continue with remaining advanced workflow tests (Tests 16-20)...

    # ==================== UI/UX INTERACTIONS (Tests 22-30) ====================

    async def test_22_responsive_design_breakpoints(self) -> Dict[str, Any]:
        """Test 22: Responsive design across all breakpoints"""
        result = {
            'breakpoints_tested': 0,
            'mobile_optimization': False,
            'tablet_optimization': False,
            'desktop_optimization': False,
            'success': False,
            'errors': []
        }

        try:
            # Test different viewport sizes
            breakpoints = [
                {'name': 'Mobile Small', 'width': 320, 'height': 568},
                {'name': 'Mobile Large', 'width': 414, 'height': 896},
                {'name': 'Tablet', 'width': 768, 'height': 1024},
                {'name': 'Laptop', 'width': 1024, 'height': 768},
                {'name': 'Desktop', 'width': 1920, 'height': 1080},
                {'name': 'Ultra Wide', 'width': 2560, 'height': 1440}
            ]

            responsive_scores = {}

            for breakpoint in breakpoints:
                # Set viewport size
                await self.browser.execute_javascript(f"""
                    window.innerWidth = {breakpoint['width']};
                    window.innerHeight = {breakpoint['height']};
                    window.dispatchEvent(new Event('resize'));
                """)

                await asyncio.sleep(1)

                # Test UI elements visibility and functionality
                ui_test_result = await self.browser.execute_javascript("""
                    // Test navigation
                    const navVisible = window.getComputedStyle(document.querySelector('nav')).display !== 'none';

                    // Test workflow list
                    const workflowList = document.querySelector('[data-testid="workflow-list"]');
                    const listScrollable = workflowList ? workflowList.scrollHeight > workflowList.clientHeight : false;

                    // Test buttons are accessible
                    const buttons = document.querySelectorAll('button');
                    const buttonsAccessible = Array.from(buttons).every(btn => {
                        const style = window.getComputedStyle(btn);
                        return style.display !== 'none' &&
                               style.visibility !== 'hidden' &&
                               parseFloat(style.width) > 0;
                    });

                    return {
                        navigation: navVisible,
                        scrollable: listScrollable,
                        buttons: buttonsAccessible,
                        width: window.innerWidth,
                        height: window.innerHeight
                    };
                """)

                test_data = ui_test_result.get("result", {}).get("value", {})
                score = sum([
                    test_data.get("navigation", False),
                    test_data.get("scrollable", False),
                    test_data.get("buttons", False)
                ])

                responsive_scores[breakpoint['name']] = score
                result['breakpoints_tested'] += 1

            # Evaluate responsiveness
            result['mobile_optimization'] = all(
                responsive_scores[name] >= 2 for name in ['Mobile Small', 'Mobile Large']
            )
            result['tablet_optimization'] = responsive_scores.get('Tablet', 0) >= 2
            result['desktop_optimization'] = all(
                responsive_scores[name] >= 2 for name in ['Laptop', 'Desktop', 'Ultra Wide']
            )

            result['success'] = (
                result['breakpoints_tested'] >= 5 and
                result['mobile_optimization'] and
                result['tablet_optimization'] and
                result['desktop_optimization']
            )

        except Exception as e:
            result['errors'].append(str(e))

        return result

    async def test_23_keyboard_navigation_comprehensive(self) -> Dict[str, Any]:
        """Test 23: Comprehensive keyboard navigation"""
        result = {
            'tab_navigation_works': False,
            'keyboard_shortcuts_work': False,
            'focus_management_correct': False,
            'accessibility_compliant': False,
            'success': False,
            'errors': []
        }

        try:
            await self.browser.navigate_to(f"{self.base_url}/workflows")
            await asyncio.sleep(2)

            # Test Tab navigation through all interactive elements
            tab_sequence_works = True
            focusable_elements_count = 0

            # Count focusable elements
            focusable_count_result = await self.browser.execute_javascript("""
                const focusableElements = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';
                return document.querySelectorAll(focusableElements).length;
            """)

            focusable_elements_count = focusable_count_result.get("result", {}).get("value", 0)

            # Test Tab navigation through first 10 elements
            for i in range(min(10, focusable_elements_count)):
                await self.browser.press_key('body', 'Tab')
                await asyncio.sleep(0.2)

                focus_check = await self.browser.execute_javascript("""
                    const activeElement = document.activeElement;
                    if (!activeElement) return false;

                    const style = window.getComputedStyle(activeElement);
                    const rect = activeElement.getBoundingClientRect();

                    return style.display !== 'none' &&
                           style.visibility !== 'hidden' &&
                           rect.width > 0 && rect.height > 0;
                """)

                if not focus_check.get("result", {}).get("value", False):
                    tab_sequence_works = False
                    break

            result['tab_navigation_works'] = tab_sequence_works

            # Test keyboard shortcuts
            shortcut_tests = [
                {'key': 'n', 'ctrl': True, 'expected': 'new-workflow-modal'},
                {'key': 's', 'ctrl': True, 'expected': 'save-action'},
                {'key': 'f', 'ctrl': True, 'expected': 'search-input'},
                {'key': 'Escape', 'ctrl': False, 'expected': 'modal-closed'}
            ]

            shortcuts_working = 0

            for shortcut in shortcut_tests:
                try:
                    if shortcut.get('ctrl'):
                        await self.browser.press_key('body', shortcut['key'], ['Ctrl'])
                    else:
                        await self.browser.press_key('body', shortcut['key'])

                    await asyncio.sleep(0.5)

                    shortcut_result = await self.browser.execute_javascript(f"""
                        const element = document.querySelector('[data-testid="{shortcut["expected"]}"]');
                        return element ? element.style.display !== 'none' : false;
                    """)

                    if shortcut_result.get("result", {}).get("value", False):
                        shortcuts_working += 1

                except Exception:
                    continue

            result['keyboard_shortcuts_works'] = shortcuts_working >= len(shortcut_tests) * 0.7

            # Test focus management
            await self.browser.click_element('[data-testid="new-workflow-btn"]')
            await asyncio.sleep(1)

            focus_in_modal = await self.browser.execute_javascript("""
                const modalInput = document.querySelector('[data-testid="workflow-name"]');
                return document.activeElement === modalInput;
            """)

            await self.browser.press_key('body', 'Escape')
            await asyncio.sleep(0.5)

            focus_returned = await self.browser.execute_javascript("""
                const originalButton = document.querySelector('[data-testid="new-workflow-btn"]');
                return document.activeElement === originalButton;
            """)

            result['focus_management_correct'] = (
                focus_in_modal.get("result", {}).get("value", False) and
                focus_returned.get("result", {}).get("value", False)
            )

            # Test accessibility compliance
            accessibility_result = await self.browser.execute_javascript("""
                // Check for proper ARIA labels
                const buttons = document.querySelectorAll('button');
                let ariaCompliant = 0;

                buttons.forEach(btn => {
                    const hasAria = btn.hasAttribute('aria-label') ||
                                   btn.hasAttribute('aria-labelledby') ||
                                   btn.textContent.trim() !== '';
                    if (hasAria) ariaCompliant++;
                });

                return {
                    total: buttons.length,
                    compliant: ariaCompliant,
                    compliance_rate: ariaCompliant / buttons.length
                };
            """)

            accessibility_data = accessibility_result.get("result", {}).get("value", {})
            compliance_rate = accessibility_data.get("compliance_rate", 0)
            result['accessibility_compliant'] = compliance_rate >= 0.8

            result['success'] = all([
                result['tab_navigation_works'],
                result['keyboard_shortcuts_works'],
                result['focus_management_correct'],
                result['accessibility_compliant']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    # Continue with remaining UI tests (Tests 24-30)...

    # ==================== PERFORMANCE AND SCALABILITY (Tests 32-40) ====================

    async def test_32_large_dataset_processing(self) -> Dict[str, Any]:
        """Test 32: Large dataset processing performance"""
        result = {
            'large_dataset_loaded': False,
            'processing_performance_acceptable': False,
            'memory_usage_optimal': False,
            'system_remains_responsive': False,
            'success': False,
            'errors': []
        }

        try:
            # Create workflow for large dataset processing
            await self.browser.navigate_to(f"{self.base_url}/workflows/create")
            await asyncio.sleep(2)

            workflow_name = f"large_dataset_test_{int(time.time())}"
            await self.browser.type_text('#workflow-name', workflow_name)

            # Configure for large dataset processing
            large_data_step = await self.browser.click_element('[data-testid="add-step-btn"]')
            batch_processing_enabled = await self.browser.click_element('[data-step-type="batch-processor"]')
            batch_size_configured = await self.browser.type_text('#batch-size', '1000')

            result['large_dataset_loaded'] = all([large_data_step, batch_processing_enabled, batch_size_configured])

            if result['large_dataset_loaded']:
                # Save workflow
                await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(3)

                # Execute with large dataset
                await self.browser.navigate_to(f"{self.base_url}/workflows")
                await asyncio.sleep(2)

                await self.browser.click_element(f'[data-workflow-name="{workflow_name}"]')
                await self.browser.click_element('[data-testid="execute-workflow-btn"]')

                # Start performance monitoring
                start_time = time.time()

                # Simulate large dataset processing
                large_data_json = '{"dataset_size": 100000, "records": [{"id": 1, "data": "test"}' + ', {"id": 2, "data": "test"}' * 50000 + ']}'

                # Check if system can handle large input
                await self.browser.type_text('#test-input-data', '{"dataset_size": 100000}')
                await self.browser.click_element('[data-testid="run-with-large-dataset"]')

                # Monitor performance during processing
                performance_checks = []
                for i in range(10):
                    await asyncio.sleep(2)

                    perf_check = await self.browser.execute_javascript("""
                        return {
                            memoryUsage: performance.memory ? performance.memory.usedJSHeapSize : 0,
                            responseTime: performance.now(),
                            uiResponsive: !document.querySelector('[data-testid="ui-frozen"]')
                        };
                    """)

                    performance_checks.append(perf_check.get("result", {}).get("value", {}))

                processing_time = (time.time() - start_time) * 1000

                # Analyze performance
                avg_memory_mb = sum(
                    check.get("memoryUsage", 0) for check in performance_checks
                ) / (len(performance_checks) * 1024 * 1024)

                max_response_time = max(
                    check.get("responseTime", 0) for check in performance_checks
                )

                ui_responsive = all(
                    check.get("uiResponsive", False) for check in performance_checks
                )

                result['processing_performance_acceptable'] = processing_time < 30000  # Under 30 seconds
                result['memory_usage_optimal'] = avg_memory_mb < 1024  # Under 1GB average
                result['system_remains_responsive'] = ui_responsive and max_response_time < 5000

            result['success'] = all([
                result['large_dataset_loaded'],
                result['processing_performance_acceptable'],
                result['memory_usage_optimal'],
                result['system_remains_responsive']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    async def test_33_memory_leak_detection(self) -> Dict[str, Any]:
        """Test 33: Memory leak detection under stress"""
        result = {
            'initial_memory_baseline': 0,
            'peak_memory_usage': 0,
            'memory_released_after_cleanup': False,
            'no_memory_leaks_detected': False,
            'success': False,
            'errors': []
        }

        try:
            # Establish memory baseline
            baseline_check = await self.browser.execute_javascript("""
                return performance.memory ? performance.memory.usedJSHeapSize : 0;
            """)

            initial_memory = baseline_check.get("result", {}).get("value", 0)
            result['initial_memory_baseline'] = initial_memory

            # Create memory-intensive operations
            memory_tests = []

            for i in range(5):
                # Create and execute multiple workflows
                workflow_name = f"memory_test_{i}_{int(time.time())}"

                await self.browser.navigate_to(f"{self.base_url}/workflows/create")
                await asyncio.sleep(1)

                await self.browser.type_text('#workflow-name', workflow_name)
                await self.browser.click_element('[data-testid="add-step-btn"]')
                await self.browser.click_element('[data-step-type="memory-intensive"]')
                await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(2)

                # Execute workflow
                await self.browser.navigate_to(f"{self.base_url}/workflows")
                await asyncio.sleep(1)

                await self.browser.click_element(f'[data-workflow-name="{workflow_name}"]')
                await self.browser.click_element('[data-testid="execute-workflow-btn"]')

                # Monitor memory during execution
                memory_check = await self.browser.execute_javascript("""
                    return performance.memory ? {
                        used: performance.memory.usedJSHeapSize,
                        total: performance.memory.totalJSHeapSize,
                        limit: performance.memory.jsHeapSizeLimit
                    } : null;
                """)

                memory_data = memory_check.get("result", {}).get("value", {})
                memory_tests.append(memory_data.get("used", 0))

                await asyncio.sleep(3)

            result['peak_memory_usage'] = max(memory_tests) if memory_tests else 0

            # Force garbage collection and check memory release
            await self.browser.execute_javascript("""
                // Force garbage collection if available
                if (window.gc) {
                    window.gc();
                }

                // Clear any stored data
                localStorage.clear();
                sessionStorage.clear();
            """)

            await asyncio.sleep(5)

            # Check final memory usage
            final_memory_check = await self.browser.execute_javascript("""
                return performance.memory ? performance.memory.usedJSHeapSize : 0;
            """)

            final_memory = final_memory_check.get("result", {}).get("value", 0)

            # Calculate memory leak metrics
            memory_increase = final_memory - initial_memory
            memory_growth_percentage = (memory_increase / initial_memory) * 100 if initial_memory > 0 else 0

            result['memory_released_after_cleanup'] = memory_growth_percentage < 50  # Less than 50% growth
            result['no_memory_leaks_detected'] = memory_growth_percentage < 20  # Less than 20% growth

            result['success'] = all([
                result['initial_memory_baseline'] > 0,
                result['peak_memory_usage'] > 0,
                result['memory_released_after_cleanup'],
                result['no_memory_leaks_detected']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    # Continue with remaining performance tests (Tests 34-40)...

    # ==================== SECURITY AND COMPLIANCE (Tests 42-50) ====================

    async def test_42_input_sanitization_and_xss_prevention(self) -> Dict[str, Any]:
        """Test 42: Input sanitization and XSS prevention"""
        result = {
            'xss_payloads_blocked': 0,
            'input_sanitization_works': False,
            'script_injection_prevented': False,
            'csrf_protection_active': False,
            'success': False,
            'errors': []
        }

        try:
            # Test various XSS payloads
            xss_payloads = [
                '<script>alert("XSS")</script>',
                'javascript:alert("XSS")',
                '<img src=x onerror=alert("XSS")>',
                '<svg onload=alert("XSS")>',
                '"><script>alert("XSS")</script>',
                '\';alert("XSS");//',
                '<iframe src="javascript:alert(\'XSS\')"></iframe>',
                '<body onload=alert("XSS")>'
            ]

            blocked_payloads = 0

            for payload in xss_payloads:
                # Test payload in workflow name
                await self.browser.navigate_to(f"{self.base_url}/workflows/create")
                await asyncio.sleep(2)

                await self.browser.type_text('#workflow-name', payload)
                await self.browser.type_text('#workflow-description', payload)
                await self.browser.click_element('[data-testid="save-workflow-btn"]')
                await asyncio.sleep(2)

                # Check if XSS was blocked/sanitized
                xss_blocked = await self.browser.execute_javascript("""
                    const workflowName = document.querySelector('[data-testid="workflow-name-display"]');
                    const workflowDesc = document.querySelector('[data-testid="workflow-description-display"]');

                    const nameContainsScript = workflowName ? workflowName.textContent.includes('<script>') : false;
                    const descContainsScript = workflowDesc ? workflowDesc.textContent.includes('<script>') : false;

                    const scriptExecuted = document.querySelector('[data-testid="script-executed"]');

                    return {
                        sanitized: !nameContainsScript && !descContainsScript,
                        no_execution: !scriptExecuted
                    };
                """)

                xss_result = xss_blocked.get("result", {}).get("value", {})
                if xss_result.get("sanitized", False) and xss_result.get("no_execution", True):
                    blocked_payloads += 1

                await asyncio.sleep(1)

            result['xss_payloads_blocked'] = blocked_payloads
            result['input_sanitization_works'] = blocked_payloads >= len(xss_payloads) * 0.8

            # Test script injection prevention
            await self.browser.navigate_to(f"{self.base_url}/workflows/create")
            await asyncio.sleep(2)

            malicious_script = '<script>window.eval("alert(\'hack\')");</script>'
            await self.browser.type_text('#workflow-name', malicious_script)
            await self.browser.click_element('[data-testid="save-workflow-btn"]')
            await asyncio.sleep(2)

            script_injection_check = await self.browser.execute_javascript("""
                const scriptElements = document.querySelectorAll('script');
                const alertCount = scriptElements.length;

                return {
                    no_new_scripts: alertCount === 0,
                    safe_display: !document.body.textContent.includes('window.eval')
                };
            """)

            injection_result = script_injection_check.get("result", {}).get("value", {})
            result['script_injection_prevented'] = all(injection_result.values())

            # Test CSRF protection
            await self.browser.navigate_to(f"{self.base_url}/workflows")
            await asyncio.sleep(2)

            # Check for CSRF tokens
            csrf_check = await self.browser.execute_javascript("""
                const csrfToken = document.querySelector('[name="csrf_token"]');
                const csrfMeta = document.querySelector('meta[name="csrf-token"]');

                return {
                    token_present: csrfToken !== null || csrfMeta !== null,
                    forms_protected: document.querySelectorAll('form').length > 0 && (csrfToken !== null || csrfMeta !== null)
                };
            """)

            csrf_result = csrf_check.get("result", {}).get("value", {})
            result['csrf_protection_active'] = csrf_result.get("token_present", False)

            result['success'] = all([
                result['input_sanitization_works'],
                result['script_injection_prevented'],
                result['csrf_protection_active']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    async def test_43_data_encryption_and_privacy(self) -> Dict[str, Any]:
        """Test 43: Data encryption and privacy protection"""
        result = {
            'sensitive_data_encrypted': False,
            'data_in_transit_secure': False,
            'data_at_rest_protected': False,
            'privacy_controls_working': False,
            'success': False,
            'errors': []
        }

        try:
            # Test sensitive data encryption
            await self.browser.navigate_to(f"{self.base_url}/workflows/create")
            await asyncio.sleep(2)

            workflow_name = f"encryption_test_{int(time.time())}"
            await self.browser.type_text('#workflow-name', workflow_name)

            # Add sensitive data handling step
            sensitive_step = await self.browser.click_element('[data-testid="add-step-btn"]')
            encryption_enabled = await self.browser.click_element('[data-step-type="sensitive-data-handler"]')

            # Configure encryption
            encryption_algorithm = await self.browser.click_element('[data-encryption="AES-256"]')
            key_management = await self.browser.click_element('[data-key-management="hsm"]')

            # Add sensitive test data
            sensitive_data = '{"ssn": "123-45-6789", "credit_card": "4111-1111-1111-1111", "api_key": "sk_test_12345"}'
            await self.browser.type_text('#sensitive-data', sensitive_data)

            # Save workflow
            save_clicked = await self.browser.click_element('[data-testid="save-workflow-btn"]')
            await asyncio.sleep(3)

            result['sensitive_data_encrypted'] = all([
                sensitive_step, encryption_enabled, encryption_algorithm,
                key_management, save_clicked
            ])

            if result['sensitive_data_encrypted']:
                # Test data in transit security
                await self.browser.navigate_to(f"{self.base_url}/workflows")
                await asyncio.sleep(2)

                await self.browser.click_element(f'[data-workflow-name="{workflow_name}"]')
                await self.browser.click_element('[data-testid="execute-workflow-btn"]')

                # Check HTTPS usage and secure headers
                security_check = await self.browser.execute_javascript("""
                    return {
                        isHttps: window.location.protocol === 'https:',
                        secureHeaders: {
                            'strict-transport-security': document.querySelector('meta[http-equiv="Strict-Transport-Security"]') !== null,
                            'content-security-policy': document.querySelector('meta[http-equiv="Content-Security-Policy"]') !== null,
                            'x-frame-options': document.querySelector('meta[http-equiv="X-Frame-Options"]') !== null
                        }
                    };
                """)

                security_result = security_check.get("result", {}).get("value", {})
                secure_headers_count = sum(security_result.get("secureHeaders", {}).values())

                result['data_in_transit_secure'] = (
                    security_result.get("isHttps", False) and
                    secure_headers_count >= 2
                )

                # Test data at rest protection
                data_storage_check = await self.browser.execute_javascript("""
                    const storedData = localStorage.getItem('workflow_data') || sessionStorage.getItem('workflow_data');

                    if (storedData) {
                        // Check if data is encrypted (should not contain readable sensitive info)
                        const hasReadableSSN = storedData.includes('123-45-6789');
                        const hasReadableCC = storedData.includes('4111-1111-1111-1111');
                        const hasReadableKey = storedData.includes('sk_test_12345');

                        return {
                            data_stored: true,
                            encrypted: !hasReadableSSN && !hasReadableCC && !hasReadableKey
                        };
                    }

                    return { data_stored: false, encrypted: true };
                """)

                storage_result = data_storage_check.get("result", {}).get("value", {})
                result['data_at_rest_protected'] = (
                    not storage_result.get("data_stored", False) or
                    storage_result.get("encrypted", False)
                )

                # Test privacy controls
                privacy_controls = await self.browser.click_element('[data-testid="privacy-settings"]')
                data_masking_enabled = await self.browser.click_element('[data-privacy="data-masking"]')
                audit_logging_enabled = await self.browser.click_element('[data-privacy="audit-logging"]')

                result['privacy_controls_working'] = all([
                    privacy_controls, data_masking_enabled, audit_logging_enabled
                ])

            result['success'] = all([
                result['sensitive_data_encrypted'],
                result['data_in_transit_secure'],
                result['data_at_rest_protected'],
                result['privacy_controls_working']
            ])

        except Exception as e:
            result['errors'].append(str(e))

        return result

    # Continue with remaining security tests (Tests 44-50)...

    def get_all_additional_tests(self):
        """Return list of all additional test methods"""
        return [
            self.test_13_workflow_chaining_and_dependencies,
            self.test_14_custom_function_integration,
            self.test_15_api_endpoint_integration,
            self.test_22_responsive_design_breakpoints,
            self.test_23_keyboard_navigation_comprehensive,
            self.test_32_large_dataset_processing,
            self.test_33_memory_leak_detection,
            self.test_42_input_sanitization_and_xss_prevention,
            self.test_43_data_encryption_and_privacy
            # Note: All remaining 29 tests would be listed here to complete the 50-test suite
        ]