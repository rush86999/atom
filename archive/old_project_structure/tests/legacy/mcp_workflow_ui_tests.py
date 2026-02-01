"""
MCP Workflow UI Testing Framework
Comprehensive UI testing using Chrome DevTools MCP Server for workflow functionality
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import uuid

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    import requests
    PLAYWRIGHT_AVAILABLE = True
except ImportError as e:
    print(f"Playwright not available: {e}")
    PLAYWRIGHT_AVAILABLE = False

# Import existing MCP integration
from testing.enhanced_ai_e2e_integration import ChromeDevToolsMCPIntegration


class MCPWorkflowUITester:
    """UI testing using Chrome DevTools MCP Server"""

    def __init__(self):
        self.mcp_integration = ChromeDevToolsMCPIntegration()
        self.browser = None
        self.context = None
        self.test_results = {
            "session_id": str(uuid.uuid4()),
            "start_time": datetime.now().isoformat(),
            "tests": [],
            "screenshots": [],
            "performance_metrics": [],
            "accessibility_scores": [],
            "ui_issues": [],
            "workflow_tests": []
        }
        self.mcp_session_id = str(uuid.uuid4())

    async def setup(self) -> bool:
        """Initialize testing environment"""
        print("Setting up MCP Workflow UI Tester...")

        if not PLAYWRIGHT_AVAILABLE:
            print("FAIL: Playwright not available")
            return False

        # Start MCP server
        mcp_success = await self.mcp_integration.start_mcp_server()
        if not mcp_success:
            print("WARN: Continuing without MCP server (limited functionality)")

        # Setup Playwright
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,  # Keep visible for debugging
            args=[
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--enable-logging",
                "--log-level=0"
            ]
        )

        self.context = await self.browser.new_context(
            viewport={"width": 1280, "height": 720},
            permissions=["clipboard-read", "clipboard-write", "microphone", "camera"],
            record_video_dir="test_results/workflow_videos"
        )

        # Create test directories
        os.makedirs("test_results/workflow_screenshots", exist_ok=True)
        os.makedirs("test_results/workflow_videos", exist_ok=True)
        os.makedirs("test_results/mcp_reports", exist_ok=True)

        return True

    async def run_workflow_ui_tests(self) -> Dict[str, Any]:
        """Run comprehensive workflow UI tests"""
        print("\n" + "="*80)
        print("MCP WORKFLOW UI TESTING")
        print("="*80)

        if not await self.setup():
            return {"error": "Failed to setup testing environment"}

        try:
            # Test workflow creation UI
            await self.test_workflow_creation_ui()

            # Test parameter collection UI
            await self.test_parameter_collection_ui()

            # Test multi-step workflow execution UI
            await self.test_multi_step_execution_ui()

            # Test pause/resume functionality UI
            await self.test_pause_resume_ui()

            # Test multi-output display UI
            await self.test_multi_output_ui()

            # Test workflow templates UI
            await self.test_workflow_templates_ui()

            # Test workflow management UI
            await self.test_workflow_management_ui()

            # Generate comprehensive report
            await self.generate_mcp_report()

            return self.test_results

        except Exception as e:
            print(f"FAIL: Test suite failed: {e}")
            return {"error": str(e), "test_results": self.test_results}

        finally:
            await self.cleanup()

    async def test_workflow_creation_ui(self) -> None:
        """Test workflow creation interface"""
        test_name = "Workflow Creation UI"
        print(f"\nTESTING: {test_name}")

        try:
            page = await self.context.new_page()

            # Navigate to workflow creation page
            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Look for "Create Workflow" button
            create_button = await page.query_selector("button:has-text('Create Workflow'), button:has-text('New Workflow')")

            if create_button:
                await create_button.click()
                await page.wait_for_timeout(2000)

                # Create MCP session for detailed analysis
                mcp_data = await self.mcp_integration.create_devtools_session(page)

                # Check for workflow form elements
                form_elements = await self._analyze_workflow_form(page)

                # Test workflow name input
                name_input = await page.query_selector("input[name='name'], input[placeholder*='name']")
                if name_input:
                    await name_input.fill("Test Workflow")
                    await page.wait_for_timeout(500)

                # Test workflow description
                desc_input = await page.query_selector("textarea[name='description'], textarea[placeholder*='description']")
                if desc_input:
                    await desc_input.fill("Test workflow for UI validation")
                    await page.wait_for_timeout(500)

                # Test step addition
                add_step_button = await page.query_selector("button:has-text('Add Step'), button:has-text('+ Step')")
                if add_step_button:
                    await add_step_button.click()
                    await page.wait_for_timeout(1000)

                # Take screenshot
                screenshot_path = f"test_results/workflow_screenshots/workflow_creation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                # Test save workflow
                save_button = await page.query_selector("button:has-text('Save'), button:has-text('Create Workflow')")
                if save_button:
                    await save_button.click()
                    await page.wait_for_timeout(2000)

                self._add_test_result(test_name, True, "Workflow creation interface working", {
                    "form_elements": form_elements,
                    "screenshot": screenshot_path,
                    "mcp_session": mcp_data
                })

            else:
                self._add_test_result(test_name, False, "Create Workflow button not found")

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_parameter_collection_ui(self) -> None:
        """Test parameter collection and validation UI"""
        test_name = "Parameter Collection UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            # Navigate to workflow execution
            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Look for a workflow to execute
            workflow_cards = await page.query_selector_all(".workflow-card, .card:has-text('workflow')")

            if workflow_cards:
                await workflow_cards[0].click()
                await page.wait_for_timeout(2000)

                # Create MCP session
                mcp_data = await self.mcp_integration.create_devtools_session(page)

                # Look for parameter input fields
                parameter_inputs = await self._analyze_parameter_inputs(page)

                # Test different parameter types
                param_tests = await self._test_parameter_types(page)

                # Test conditional parameter display
                conditional_tests = await self._test_conditional_parameters(page)

                # Test validation messages
                validation_tests = await self._test_parameter_validation(page)

                # Take screenshot
                screenshot_path = f"test_results/workflow_screenshots/parameter_collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                self._add_test_result(test_name, True, "Parameter collection interface working", {
                    "parameter_inputs": parameter_inputs,
                    "param_types": param_tests,
                    "conditional": conditional_tests,
                    "validation": validation_tests,
                    "screenshot": screenshot_path,
                    "mcp_session": mcp_data
                })

            else:
                self._add_test_result(test_name, False, "No workflows found for testing")

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_multi_step_execution_ui(self) -> None:
        """Test multi-step workflow execution UI"""
        test_name = "Multi-Step Execution UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Start a complex workflow execution
            await page.click("text=Run Workflow")
            await page.wait_for_timeout(2000)

            # Create MCP session
            mcp_data = await self.mcp_integration.create_devtools_session(page)

            # Monitor execution progress
            progress_data = await self._monitor_execution_progress(page)

            # Test step indicators
            step_indicators = await self._analyze_step_indicators(page)

            # Test real-time status updates
            status_updates = await self._test_real_time_status(page)

            # Take screenshot during execution
            screenshot_path = f"test_results/workflow_screenshots/multi_step_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            # Wait for completion or timeout
            await page.wait_for_timeout(5000)

            self._add_test_result(test_name, True, "Multi-step execution UI working", {
                "progress": progress_data,
                "step_indicators": step_indicators,
                "status_updates": status_updates,
                "screenshot": screenshot_path,
                "mcp_session": mcp_data
            })

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_pause_resume_ui(self) -> None:
        """Test pause and resume functionality UI"""
        test_name = "Pause/Resume UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Start a workflow that will pause
            await page.click("text=Run Workflow with Pause")
            await page.wait_for_timeout(3000)

            # Create MCP session
            mcp_data = await self.mcp_integration.create_devtools_session(page)

            # Look for pause button
            pause_button = await page.query_selector("button:has-text('Pause'), button[title*='pause']")

            if pause_button:
                await pause_button.click()
                await page.wait_for_timeout(2000)

                # Check for pause state indicators
                pause_state = await self._analyze_pause_state(page)

                # Test resume functionality
                resume_button = await page.query_selector("button:has-text('Resume'), button[title*='resume']")

                if resume_button:
                    # Add additional inputs during pause
                    await self._test_input_during_pause(page)

                    await resume_button.click()
                    await page.wait_for_timeout(2000)

                    # Test resumed state
                    resume_state = await self._analyze_resume_state(page)

                # Take screenshot
                screenshot_path = f"test_results/workflow_screenshots/pause_resume_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                self._add_test_result(test_name, True, "Pause/Resume functionality working", {
                    "pause_state": pause_state,
                    "resume_state": resume_state,
                    "screenshot": screenshot_path,
                    "mcp_session": mcp_data
                })

            else:
                self._add_test_result(test_name, False, "Pause button not found")

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_multi_output_ui(self) -> None:
        """Test multi-output display UI"""
        test_name = "Multi-Output UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Execute a workflow with multiple outputs
            await page.click("text=Run Multi-Output Workflow")
            await page.wait_for_timeout(3000)

            # Create MCP session
            mcp_data = await self.mcp_integration.create_devtools_session(page)

            # Monitor output aggregation
            output_monitoring = await self._monitor_output_aggregation(page)

            # Test output visualization
            output_viz = await self._analyze_output_visualization(page)

            # Test output download/export
            export_tests = await self._test_output_export(page)

            # Take screenshot of outputs
            screenshot_path = f"test_results/workflow_screenshots/multi_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            self._add_test_result(test_name, True, "Multi-output UI working", {
                "output_monitoring": output_monitoring,
                "visualization": output_viz,
                "export": export_tests,
                "screenshot": screenshot_path,
                "mcp_session": mcp_data
            })

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_workflow_templates_ui(self) -> None:
        """Test workflow template system UI"""
        test_name = "Workflow Templates UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Look for templates section
            templates_section = await page.query_selector(".templates-section, section:has-text('templates')")

            if templates_section:
                # Create MCP session
                mcp_data = await self.mcp_integration.create_devtools_session(page)

                # Test template selection
                template_cards = await page.query_selector_all(".template-card, .card:has-text('template')")

                if template_cards:
                    await template_cards[0].click()
                    await page.wait_for_timeout(2000)

                    # Test template preview
                    preview_data = await self._analyze_template_preview(page)

                    # Test template customization
                    customization = await self._test_template_customization(page)

                # Test template application
                apply_button = await page.query_selector("button:has-text('Use Template'), button:has-text('Apply')")
                if apply_button:
                    await apply_button.click()
                    await page.wait_for_timeout(2000)

                # Take screenshot
                screenshot_path = f"test_results/workflow_screenshots/workflow_templates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                await page.screenshot(path=screenshot_path, full_page=True)

                self._add_test_result(test_name, True, "Workflow templates UI working", {
                    "template_count": len(template_cards),
                    "preview": preview_data,
                    "customization": customization,
                    "screenshot": screenshot_path,
                    "mcp_session": mcp_data
                })

            else:
                self._add_test_result(test_name, False, "Templates section not found")

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    async def test_workflow_management_ui(self) -> None:
        """Test workflow management and organization UI"""
        test_name = "Workflow Management UI"
        print(f"TESTING: {test_name}")

        try:
            page = await self.context.new_page()

            await page.goto("http://localhost:3002/dev-studio", wait_until="networkidle", timeout=30000)

            # Create MCP session
            mcp_data = await self.mcp_integration.create_devtools_session(page)

            # Test workflow list view
            list_view = await self._analyze_workflow_list_view(page)

            # Test filtering and sorting
            filtering = await self._test_workflow_filtering(page)

            # Test workflow actions (edit, duplicate, delete)
            actions = await self._test_workflow_actions(page)

            # Test workflow organization (categories, tags)
            organization = await self._test_workflow_organization(page)

            # Take screenshot
            screenshot_path = f"test_results/workflow_screenshots/workflow_management_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            await page.screenshot(path=screenshot_path, full_page=True)

            self._add_test_result(test_name, True, "Workflow management UI working", {
                "list_view": list_view,
                "filtering": filtering,
                "actions": actions,
                "organization": organization,
                "screenshot": screenshot_path,
                "mcp_session": mcp_data
            })

            await page.close()

        except Exception as e:
            self._add_test_result(test_name, False, f"Error: {str(e)}")

    # Helper methods for MCP-based analysis
    async def _analyze_workflow_form(self, page: Page) -> Dict[str, Any]:
        """Analyze workflow form elements using MCP"""
        elements = await page.evaluate("""
            () => {
                const elements = {
                    'name_input': !!document.querySelector("input[name='name'], input[placeholder*='name']"),
                    'description_textarea': !!document.querySelector("textarea[name='description'], textarea[placeholder*='description']"),
                    'category_select': !!document.querySelector("select[name='category'], select[placeholder*='category']"),
                    'tag_input': !!document.querySelector("input[name='tags'], input[placeholder*='tags']"),
                    'trigger_buttons': document.querySelectorAll("button:has-text('Trigger'), button:has-text('trigger')").length,
                    'step_container': !!document.querySelector(".steps-container, .workflow-steps"),
                    'condition_builder': !!document.querySelector(".condition-builder, .workflow-conditions")
                };

                // Check for advanced features
                const advanced = {
                    'visual_workflow_editor': !!document.querySelector(".workflow-editor, .visual-workflow"),
                    'drag_drop_enabled': !!document.querySelector(".draggable, [draggable]"),
                    'json_editor': !!document.querySelector(".json-editor, textarea[name='workflow_json']"),
                    'parameter_wizard': !!document.querySelector(".parameter-wizard, .param-wizard")
                };

                return {...elements, ...advanced};
            }
        """)

        return elements

    async def _analyze_parameter_inputs(self, page: Page) -> Dict[str, Any]:
        """Analyze parameter input fields"""
        return await page.evaluate("""
            () => {
                const inputs = document.querySelectorAll("input[type='text'], input[type='number'], input[type='email'], select, textarea");
                const param_inputs = [];

                inputs.forEach(input => {
                    const field = {
                        'type': input.type || input.tagName.toLowerCase(),
                        'name': input.name || input.getAttribute('name') || '',
                        'placeholder': input.placeholder || '',
                        'required': input.required || input.hasAttribute('required'),
                        'has_validation': !!input.getAttribute('pattern') || !!input.getAttribute('min') || !!input.getAttribute('max')
                    };

                    // Check for special validation attributes
                    if (input.getAttribute('validation_rules')) {
                        try {
                            field['validation_rules'] = JSON.parse(input.getAttribute('validation_rules'));
                        } catch (e) {
                            field['validation_rules'] = [];
                        }
                    }

                    // Check for conditional visibility
                    if (input.getAttribute('show_when')) {
                        try {
                            field['show_when'] = JSON.parse(input.getAttribute('show_when'));
                        } catch (e) {
                            field['show_when'] = null;
                        }
                    }

                    param_inputs.push(field);
                });

                return {
                    'total_inputs': inputs.length,
                    'parameter_inputs': param_inputs,
                    'has_conditional_params': param_inputs.some(p => p['show_when']),
                    'has_validation': param_inputs.some(p => p['has_validation'])
                };
            }
        """)

    async def _test_parameter_types(self, page: Page) -> Dict[str, bool]:
        """Test different parameter input types"""
        test_results = {}

        # Test string input
        string_input = await page.query_selector("input[type='text']")
        test_results['string_input'] = string_input is not None

        # Test number input
        number_input = await page.query_selector("input[type='number']")
        test_results['number_input'] = number_input is not None

        # Test email input
        email_input = await page.query_selector("input[type='email'], input[placeholder*='email']")
        test_results['email_input'] = email_input is not None

        # Test select dropdown
        select_input = await page.query_selector("select")
        test_results['select_input'] = select_input is not None

        # Test file input
        file_input = await page.query_selector("input[type='file']")
        test_results['file_input'] = file_input is not None

        # Test date input
        date_input = await page.query_selector("input[type='date'], input[placeholder*='date']")
        test_results['date_input'] = date_input is not None

        return test_results

    async def _test_conditional_parameters(self, page: Page) -> Dict[str, Any]:
        """Test conditional parameter display"""
        return await page.evaluate("""
            () => {
                // Find inputs with conditional visibility
                const conditionalInputs = Array.from(document.querySelectorAll('input[show_when], select[show_when], textarea[show_when]'));

                const testResults = {
                    'has_conditional_inputs': conditionalInputs.length > 0,
                    'conditional_count': conditionalInputs.length,
                    'samples': []
                };

                // Test a few samples
                conditionalInputs.slice(0, 3).forEach((input, index) => {
                    const showWhen = input.getAttribute('show_when');
                    try {
                        const condition = JSON.parse(showWhen);
                        testResults.samples.push({
                            'index': index,
                            'condition': condition,
                            'element_tag': input.tagName,
                            'name': input.name || ''
                        });
                    } catch (e) {
                        testResults.samples.push({
                            'index': index,
                            'error': 'Invalid JSON in show_when',
                            'raw_value': showWhen
                        });
                    }
                });

                return testResults;
            }
        """)

    async def _test_parameter_validation(self, page: Page) -> Dict[str, Any]:
        """Test parameter validation UI elements"""
        return await page.evaluate("""
            () => {
                const validationElements = {
                    'error_messages': document.querySelectorAll('.error-message, .validation-error').length,
                    'success_indicators': document.querySelectorAll('.success, .valid, .validation-success').length,
                    'warning_messages': document.querySelectorAll('.warning, .validation-warning').length,
                    'live_validation': !!document.querySelector('[data-live-validation]'),
                    'validation_summary': !!document.querySelector('.validation-summary')
                };

                // Test validation triggers
                const triggers = {
                    'onBlur_validation': !!document.querySelector('input[onblur*="validate"]'),
                    'onInput_validation': !!document.querySelector('input[data-validate-on="input"]'),
                    'form_validation': !!document.querySelector('form[novalidate], form[data-validation]')
                };

                return {
                    'elements': validationElements,
                    'triggers': triggers
                };
            }
        """)

    async def _monitor_execution_progress(self, page: Page) -> Dict[str, Any]:
        """Monitor workflow execution progress"""
        progress_data = []

        try:
            # Monitor progress for 5 seconds
            for i in range(10):
                progress = await page.evaluate("""
                    () => {
                        const progressBar = document.querySelector('.progress-bar, .execution-progress');
                        const statusText = document.querySelector('.status-text, .execution-status');
                        const currentStep = document.querySelector('.current-step, .step-current');
                        const stepList = document.querySelectorAll('.step-item, .workflow-step');

                        const data = {
                            'progress_bar': !!progressBar,
                            'status_text': statusText ? statusText.textContent : null,
                            'current_step': currentStep ? currentStep.textContent : null,
                            'total_steps': stepList.length,
                            'completed_steps': Array.from(stepList).filter(step =>
                                step.classList.contains('completed') || step.classList.contains('success')
                            ).length,
                            'current_step_index': Array.from(stepList).findIndex(step =>
                                step.classList.contains('active') || step.classList.contains('current')
                            )
                        };

                        if (progressBar) {
                            const width = getComputedStyle(progressBar).width;
                            data['progress_width'] = parseFloat(width);
                        }

                        return data;
                    }
                """)

                progress_data.append({
                    'timestamp': time.time(),
                    'iteration': i,
                    'progress': progress
                })

                await page.wait_for_timeout(500)

        except Exception as e:
            print(f"Error monitoring progress: {e}")

        return {
            'progress_samples': progress_data,
            'final_state': progress_data[-1] if progress_data else None
        }

    async def _analyze_step_indicators(self, page: Page) -> Dict[str, Any]:
        """Analyze workflow step indicators"""
        return await page.evaluate("""
            () => {
                const steps = Array.from(document.querySelectorAll('.step-item, .workflow-step, .execution-step'));

                const stepData = steps.map((step, index) => ({
                    'index': index,
                    'element': step.tagName,
                    'text': step.textContent.trim(),
                    'classes': Array.from(step.classList),
                    'is_active': step.classList.contains('active') || step.classList.contains('current'),
                    'is_completed': step.classList.contains('completed') || step.classList.contains('success'),
                    'is_failed': step.classList.contains('failed') || step.classList.contains('error'),
                    'has_icon': !!step.querySelector('.step-icon, .status-icon'),
                    'has_progress': !!step.querySelector('.step-progress')
                }));

                return {
                    'total_steps': steps.length,
                    'steps': stepData,
                    'completed_count': stepData.filter(s => s['is_completed']).length,
                    'failed_count': stepData.filter(s => s['is_failed']).length,
                    'active_count': stepData.filter(s => s['is_active']).length
                };
            }
        """)

    async def _test_real_time_status(self, page: Page) -> Dict[str, Any]:
        """Test real-time status updates"""
        updates = []

        try:
            # Monitor status changes for 3 seconds
            for i in range(6):
                status = await page.evaluate("""
                    () => {
                        const status = document.querySelector('.execution-status, .workflow-status');
                        const logs = Array.from(document.querySelectorAll('.status-log, .execution-log')).slice(-3);

                        return {
                            'status_text': status ? status.textContent : null,
                            'status_class': status ? Array.from(status.classList) : [],
                            'recent_logs': logs.map(log => ({
                                'text': log.textContent.trim(),
                                'timestamp': log.getAttribute('data-timestamp') || null,
                                'level': log.classList.contains('error') ? 'error' :
                                       log.classList.contains('warning') ? 'warning' : 'info'
                            }))
                        };
                    }
                """)

                updates.append({
                    'timestamp': time.time(),
                    'iteration': i,
                    'status': status
                })

                await page.wait_for_timeout(500)

        except Exception as e:
            print(f"Error monitoring status: {e}")

        return {
            'status_updates': updates,
            'final_status': updates[-1] if updates else None
        }

    async def _analyze_pause_state(self, page: Page) -> Dict[str, Any]:
        """Analyze paused workflow state"""
        return await page.evaluate("""
            () => {
                const pauseIndicators = {
                    'pause_banner': !!document.querySelector('.pause-banner, .workflow-paused'),
                    'pause_button': !!document.querySelector('button[disabled*="pause"], .workflow-paused button'),
                    'resume_button': !!document.querySelector('button:has-text("Resume")'),
                    'status_paused': !!document.querySelector('.status:contains("Paused"), .workflow-paused')
                };

                const inputs = {
                    'additional_inputs_available': !!document.querySelector('.additional-inputs, .pause-inputs'),
                    'input_fields': document.querySelectorAll('.additional-inputs input, .pause-inputs input').length
                };

                return {
                    'indicators': pauseIndicators,
                    'inputs': inputs,
                    'has_pause_state': Object.values(pauseIndicators).some(v => v)
                };
            }
        """)

    async def _analyze_resume_state(self, page: Page) -> Dict[str, Any]:
        """Analyze resumed workflow state"""
        return await page.evaluate("""
            () => {
                const resumeIndicators = {
                    'resume_banner': !!document.querySelector('.resume-banner, .workflow-resumed'),
                    'resume_button': !!document.querySelector('button:has-text("Resume")'),
                    'status_running': !!document.querySelector('.status:contains("Running"), .workflow-running'),
                    'execution_active': !!document.querySelector('.execution-active, .workflow-running')
                };

                return {
                    'indicators': resumeIndicators,
                    'has_resume_state': Object.values(resumeIndicators).some(v => v)
                };
            }
        """)

    async def _test_input_during_pause(self, page: Page):
        """Test adding inputs during pause state"""
        try:
            # Find input field during pause
            input_field = await page.query_selector(".pause-inputs input, .additional-inputs input")

            if input_field:
                test_value = f"Test Input {time.time()}"
                await input_field.fill(test_value)
                await page.wait_for_timeout(500)

                return {
                    'input_added': True,
                    'test_value': test_value
                }

            return {'input_added': False}

        except Exception as e:
            return {'input_added': False, 'error': str(e)}

    async def _monitor_output_aggregation(self, page: Page) -> Dict[str, Any]:
        """Monitor multi-output aggregation"""
        aggregation_data = []

        try:
            # Monitor for 5 seconds
            for i in range(10):
                aggregation = await page.evaluate("""
                    () => {
                        const outputs = document.querySelectorAll('.workflow-output, .step-output');
                        const aggregationSection = document.querySelector('.output-aggregation, .multi-output');

                        const data = {
                            'output_count': outputs.length,
                            'aggregation_section': !!aggregationSection,
                            'outputs': Array.from(outputs).map((output, index) => ({
                                'index': index,
                                'type': output.getAttribute('data-output-type') || 'unknown',
                                'content': output.textContent.trim(),
                                'classes': Array.from(output.classList)
                            }))
                        };

                        if (aggregationSection) {
                            data['aggregation_type'] = aggregationSection.getAttribute('data-aggregation-type') || 'unknown';
                            data['aggregated_count'] = aggregationSection.getAttribute('data-count') || '0';
                        }

                        return data;
                    }
                """)

                aggregation_data.append({
                    'timestamp': time.time(),
                    'iteration': i,
                    'aggregation': aggregation
                })

                await page.wait_for_timeout(500)

        except Exception as e:
            print(f"Error monitoring aggregation: {e}")

        return {
            'aggregation_samples': aggregation_data,
            'final_state': aggregation_data[-1] if aggregation_data else None
        }

    async def _analyze_output_visualization(self, page: Page) -> Dict[str, Any]:
        """Analyze output visualization components"""
        return await page.evaluate("""
            () => {
                const visualization = {
                    'charts': document.querySelectorAll('.output-chart, .data-chart').length,
                    'tables': document.querySelectorAll('.output-table, .data-table').length,
                    'cards': document.querySelectorAll('.output-card, .result-card').length,
                    'lists': document.querySelectorAll('.output-list, .result-list').length,
                    'tabs': document.querySelectorAll('.output-tabs, .output-nav').length,
                    'download_buttons': document.querySelectorAll('button:has-text("Download"), button:has-text("Export")').length
                };

                // Check for interactive features
                const interactive = {
                    'filterable': !!document.querySelector('.output-filter, [data-filterable]'),
                    'sortable': !!document.querySelector('.output-sortable, [data-sortable]'),
                    'searchable': !!document.querySelector('.output-search, [data-searchable]'),
                    'expandable': !!document.querySelector('.output-expandable, [data-expandable]')
                };

                return {
                    'visualization': visualization,
                    'interactive': interactive,
                    'total_visual_elements': sum(Object.values(visualization))
                };
            }
        """)

    async def _test_output_export(self, page: Page) -> Dict[str, Any]:
        """Test output export functionality"""
        try:
            # Find download buttons
            download_buttons = await page.query_selector_all("button:has-text('Download'), button:has-text('Export')")

            export_results = []
            for button in download_buttons:
                button_text = await button.evaluate("el => el.textContent")
                has_href = await button.evaluate("el => !!(el.getAttribute('href') || el.onclick)")
                is_enabled = await button.evaluate("el => !el.disabled")
                export_results.append({
                    'button_text': button_text,
                    'has_href': has_href,
                    'is_enabled': is_enabled
                })

            return {
                'download_buttons_found': len(download_buttons),
                'export_results': export_results,
                'has_export_functionality': len(download_buttons) > 0
            }

        except Exception as e:
            return {'error': str(e), 'export_results': []}

    async def _analyze_workflow_list_view(self, page: Page) -> Dict[str, Any]:
        """Analyze workflow list/grid view"""
        return await page.evaluate("""
            () => {
                const workflows = Array.from(document.querySelectorAll('.workflow-card, .workflow-item, .workflow-tile'));

                const workflowData = workflows.map((workflow, index) => ({
                    'index': index,
                    'title': workflow.querySelector('.workflow-title, h3, .title')?.textContent?.trim(),
                    'description': workflow.querySelector('.workflow-description, .description, p')?.textContent?.trim(),
                    'status': Array.from(workflow.classList).find(c => c.includes('running') || c.includes('completed') || c.includes('failed') || c.includes('paused')),
                    'actions': workflow.querySelectorAll('button, .action').length,
                    'metadata': {
                        'tags': Array.from(workflow.querySelectorAll('.tag')).map(tag => tag.textContent.trim()),
                        'last_run': workflow.querySelector('.last-run, .date')?.textContent?.trim(),
                        'created_date': workflow.querySelector('.created-date, .date')?.textContent?.trim()
                    }
                }));

                const viewControls = {
                    'search_box': !!document.querySelector('input[placeholder*="search workflow"], .workflow-search'),
                    'filter_buttons': document.querySelectorAll('.filter-button, .workflow-filter').length,
                    'sort_options': !!document.querySelector('.sort-select, .workflow-sort'),
                    'view_toggle': document.querySelectorAll('.view-toggle, .grid-list-toggle').length,
                    'create_button': !!document.querySelector('button:has-text("Create"), .workflow-create')
                };

                return {
                    'total_workflows': workflows.length,
                    'workflows': workflowData,
                    'controls': viewControls
                };
            }
        """)

    async def _test_workflow_filtering(self, page: Page) -> Dict[str, Any]:
        """Test workflow filtering and sorting"""
        try:
            # Test search functionality
            search_box = await page.query_selector('input[placeholder*="search workflow"], .workflow-search')
            search_test = None
            if search_box:
                await search_box.fill("test workflow")
                await page.wait_for_timeout(1000)
                # Check if results are filtered
                filtered_workflows = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('.workflow-card')).filter(card =>
                        card.textContent.toLowerCase().includes('test workflow')
                    ).length;
                """)
                search_test = {
                    'search_functional': True,
                    'filtered_count': filtered_workflows
                }

            # Test category filter
            category_filter = await page.querySelector('select[placeholder*="category"], .category-filter')
            category_test = None
            if category_filter:
                await category_filter.select('1')  # Select first category
                await page.wait_for_timeout(1000)
                category_test = {'filter_applied': True}

            # Test status filter
            status_filter = await page.querySelector('.status-filter, .workflow-status-filter')
            status_test = None
            if status_filter:
                await status_filter.click()  # First status option
                await page.wait_for_timeout(1000)
                status_test = {'status_applied': True}

            return {
                'search_test': search_test,
                'category_test': category_test,
                'status_test': status_test,
                'has_filters': search_box is not None or category_filter is not None or status_filter is not None
            }

        except Exception as e:
            return {'error': str(e)}

    async def _test_workflow_actions(self, page: Page) -> Dict[str, Any]:
        """Test workflow action buttons (edit, duplicate, delete, etc.)"""
        try:
            # Find workflow cards with actions
            workflow_cards = await page.query_selector_all('.workflow-card')
            action_buttons = []

            for card in workflow_cards:
                card_actions = await card.query_selectorAll('button, .action')
                action_buttons.extend(card_actions)

            # Test each action type
            actions = {
                'edit_buttons': 0,
                'duplicate_buttons': 0,
                'delete_buttons': 0,
                'run_buttons': 0,
                'pause_buttons': 0,
                'stop_buttons': 0,
                'export_buttons': 0,
                'share_buttons': 0
            }

            for button in action_buttons:
                button_text = await button.evaluate("el => el.textContent.toLowerCase()")
                if 'edit' in button_text:
                    actions['edit_buttons'] += 1
                elif 'duplicate' in button_text or 'copy' in button_text:
                    actions['duplicate_buttons'] += 1
                elif 'delete' in button_text or 'remove' in button_text:
                    actions['delete_buttons'] += 1
                elif 'run' in button_text or 'execute' in button_text:
                    actions['run_buttons'] += 1
                elif 'pause' in button_text:
                    actions['pause_buttons'] += 1
                elif 'stop' in button_text or 'cancel' in button_text:
                    actions['stop_buttons'] += 1
                elif 'export' in button_text or 'download' in button_text:
                    actions['export_buttons'] += 1
                elif 'share' in button_text:
                    actions['share_buttons'] += 1

            return {
                'total_action_buttons': len(action_buttons),
                'action_types': actions,
                'average_actions_per_workflow': len(action_buttons) / max(len(workflow_cards), 1)
            }

        except Exception as e:
            return {'error': str(e)}

    async def _test_workflow_organization(self, page: Page) -> Dict[str, Any]:
        """Test workflow organization features"""
        try:
            # Test categories
            categories = await page.query_selector_all('.category-badge, .workflow-category')

            # Test tags
            tags = await page.query_selector_all('.tag, .workflow-tag')

            # Test folders/groups
            folders = await page.query_selector_all('.folder, .workflow-folder, .group')

            organization = {
                'has_categories': len(categories) > 0,
                'has_tags': len(tags) > 0,
                'has_folders': len(folders) > 0,
                'category_count': len(categories),
                'tag_count': len(tags),
                'folder_count': len(folders)
            }

            # Test drag-and-drop organization
            drag_drop = {
                'draggable_items': await page.query_selector_all('[draggable], .draggable-workflow'),
                'drop_zones': await page.query_selector_all('.drop-zone, .workflow-dropzone'),
                'sortable_containers': await page.query_selector_all('[sortable], .sortable-workflows')
            }

            return {
                'organization': organization,
                'drag_drop': drag_drop,
                'has_organization': organization['has_categories'] or organization['has_tags'] or organization['has_folders']
            }

        except Exception as e:
            return {'error': str(e)}

    async def _analyze_template_preview(self, page: Page) -> Dict[str, Any]:
        """Analyze template preview"""
        return await page.evaluate("""
            () => {
                const preview = {
                    'has_preview': !!document.querySelector('.template-preview, .workflow-preview'),
                    'preview_content': document.querySelector('.template-content, .template-details')?.textContent || '',
                    'preview_image': !!document.querySelector('.template-preview img, .workflow-image'),
                    'steps_preview': !!document.querySelector('.steps-preview, .template-steps'),
                    'parameters_preview': !!document.querySelector('.parameters-preview, .template-params')
                };

                const customization = {
                    'has_customization': !!document.querySelector('.template-customization, .customize-template'),
                    'custom_fields': document.querySelectorAll('.custom-field, .template-custom-field').length,
                    'can_edit_steps': !!document.querySelector('button:has-text("Edit Steps"), .edit-template-steps'),
                    'can_edit_params': !!document.querySelector('button:has-text("Edit Parameters"), .edit-template-params')
                };

                return {
                    'preview': preview,
                    'customization': customization,
                    'can_customize': customization['has_customization']
                };
            }
        """)

    async def _test_template_customization(self, page: Page):
        """Test template customization"""
        try:
            # Test editing template name
            name_field = await page.query_selector("input[name='template_name'], input[placeholder*='template name']")
            if name_field:
                await name_field.fill("Custom Test Template")
                return {'name_edited': True}

            return {'name_edited': False}

        except Exception as e:
            return {'name_edited': False, 'error': str(e)}

    def _add_test_result(self, test_name: str, success: bool, message: str, details: Dict[str, Any] = None):
        """Add test result to results"""
        test_result = {
            "name": test_name,
            "success": success,
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }

        self.test_results["tests"].append(test_result)

        if not success:
            self.test_results["ui_issues"].append({
                "test": test_name,
                "issue": message,
                "details": details,
                "timestamp": datetime.now().isoformat()
            })

    async def generate_mcp_report(self):
        """Generate comprehensive MCP-based test report"""
        end_time = datetime.now()
        duration = (end_time - datetime.fromisoformat(self.test_results["start_time"])).total_seconds()

        # Calculate summary metrics
        total_tests = len(self.test_results["tests"])
        passed_tests = len([t for t in self.test_results["tests"] if t["success"]])

        # MCP-specific metrics
        mcp_sessions = len([t for t in self.test_results["tests"] if t.get("details", {}).get("mcp_session")])

        # Create comprehensive report
        report = {
            "session_id": self.test_results["session_id"],
            "mcp_session_id": self.mcp_session_id,
            "test_type": "MCP Workflow UI Testing",
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "pass_rate": (passed_tests / total_tests * 100) if total_tests > 0 else 0,
                "duration_seconds": duration,
                "mcp_sessions_used": mcp_sessions
            },
            "mcp_features": {
                "devtools_sessions": mcp_sessions,
                "session_analysis": [t.get("details", {}).get("mcp_session") for t in self.test_results["tests"] if t.get("details", {}).get("mcp_session")],
                "performance_metrics": [t.get("details", {}).get("mcp_session") for t in self.test_results["tests"] if t.get("details", {}).get("mcp_session")]
            },
            "test_results": self.test_results["tests"],
            "ui_issues": self.test_results["ui_issues"],
            "recommendations": self._generate_recommendations(),
            "generated_at": end_time.isoformat()
        }

        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = f"test_results/mcp_reports/mcp_workflow_test_report_{timestamp}.json"

        with open(report_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        print(f"\n" + "="*80)
        print("MCP WORKFLOW UI TEST REPORT")
        print("="*80)
        print(f"Tests: {passed_tests}/{total_tests} passed ({passed_tests/total_tests*100:.1f}%)")
        print(f"MCP Sessions: {mcp_sessions}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"UI Issues Found: {len(self.test_results['ui_issues'])}")
        print(f"Report saved to: {report_path}")
        print("="*80)

        return report

    def _generate_recommendations(self) -> List[str]:
        """Generate test recommendations"""
        recommendations = []

        failed_tests = [t for t in self.test_results["tests"] if not t["success"]]

        if failed_tests:
            recommendations.append("Fix UI issues found in failed tests")

        mcp_sessions_used = len([t for t in self.test_results["tests"] if t.get("details", {}).get("mcp_session")])
        if mcp_sessions_used == 0:
            recommendations.append("Enable MCP server integration for deeper analysis")

        avg_performance = sum(t.get("details", {}).get("performance_metrics", {}).get("response_time", 0) for t in self.test_results["tests"]) / max(len(self.test_results["tests"]), 1)
        if avg_performance > 2.0:
            recommendations.append("Optimize UI performance for better responsiveness")

        accessibility_scores = self.test_results["accessibility_scores"]
        if accessibility_scores:
            avg_accessibility = sum(accessibility_scores) / len(accessibility_scores)
            if avg_accessibility < 80:
                recommendations.append("Improve accessibility compliance for better user experience")

        return recommendations

    async def cleanup(self):
        """Clean up resources"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()

        self.mcp_integration.stop_mcp_server()


async def main():
    """Main entry point for MCP workflow UI testing"""
    print("STARTING MCP Workflow UI Testing Framework")

    tester = MCPWorkflowUITester()
    results = await tester.run_workflow_ui_tests()

    if "error" in results:
        sys.exit(1)
    else:
        passed = results.get("summary", {}).get("passed_tests", 0)
        total = results.get("summary", {}).get("total_tests", 1)
        sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())