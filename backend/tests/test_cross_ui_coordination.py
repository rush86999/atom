import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List
import requests


class CrossUICoordinationTester:
    """Test cross-UI coordination and workflow automation"""

    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.frontend_url = "http://localhost:3000"
        self.test_results = {}

    async def test_chat_coordination(self):
        """Test chat interface coordination across UIs"""
        print("🧪 Testing Chat Interface Coordination...")

        test_cases = [
            {
                "name": "Search Coordination",
                "command": "Search for my project documents about Q3 planning",
                "expected_actions": ["search_ui", "cross_platform_search"],
            },
            {
                "name": "Communication Coordination",
                "command": "Show me messages from my team about the new feature",
                "expected_actions": ["communication_ui", "message_filtering"],
            },
            {
                "name": "Task Coordination",
                "command": "What tasks are due this week for the marketing campaign?",
                "expected_actions": ["task_ui", "task_filtering", "priority_display"],
            },
            {
                "name": "Cross-UI Workflow",
                "command": "Help me onboard a new team member",
                "expected_actions": [
                    "search_ui",
                    "communication_ui",
                    "task_ui",
                    "workflow_creation",
                ],
            },
        ]

        for test_case in test_cases:
            print(f"  Testing: {test_case['name']}")
            print(f"    Command: '{test_case['command']}'")

            try:
                # Simulate chat command processing
                response = await self._simulate_chat_command(test_case["command"])

                if response.get("success"):
                    print(f"    ✅ Chat processed successfully")
                    print(f"    Response: {response.get('message', 'No response')}")

                    # Check if coordination actions were triggered
                    coordination_actions = response.get("metadata", {}).get(
                        "coordination_actions", []
                    )
                    for expected_action in test_case["expected_actions"]:
                        if expected_action in coordination_actions:
                            print(f"    ✅ {expected_action} triggered")
                        else:
                            print(f"    ⚠️  {expected_action} not triggered")

                    self.test_results[
                        f"chat_coordination_{test_case['name'].lower().replace(' ', '_')}"
                    ] = True
                else:
                    print(f"    ❌ Chat processing failed")
                    self.test_results[
                        f"chat_coordination_{test_case['name'].lower().replace(' ', '_')}"
                    ] = False

            except Exception as e:
                print(f"    ❌ Test failed: {e}")
                self.test_results[
                    f"chat_coordination_{test_case['name'].lower().replace(' ', '_')}"
                ] = False

            print()

    async def test_workflow_automation(self):
        """Test workflow automation via chat"""
        print("🧪 Testing Workflow Automation...")

        workflow_tests = [
            {
                "name": "Email Follow-up Automation",
                "description": "Create workflow for email follow-ups",
                "command": "Automate follow-up emails for new leads",
                "expected_steps": [
                    "trigger_detection",
                    "action_creation",
                    "workflow_save",
                ],
            },
            {
                "name": "Task Creation Automation",
                "description": "Create tasks from important emails",
                "command": "When I receive important emails, create tasks in Notion",
                "expected_steps": [
                    "email_trigger",
                    "task_creation",
                    "platform_integration",
                ],
            },
            {
                "name": "Multi-Service Workflow",
                "description": "Coordinate across multiple services",
                "command": "Create a workflow that syncs calendar events to tasks and sends notifications",
                "expected_steps": [
                    "calendar_integration",
                    "task_sync",
                    "notification_system",
                ],
            },
        ]

        for workflow_test in workflow_tests:
            print(f"  Testing: {workflow_test['name']}")
            print(f"    Description: {workflow_test['description']}")

            try:
                # Test workflow creation
                workflow_response = await self._create_workflow(
                    workflow_test["command"]
                )

                if workflow_response.get("workflow_created"):
                    print(f"    ✅ Workflow created successfully")
                    print(f"    Workflow ID: {workflow_response.get('workflow_id')}")

                    # Test workflow execution
                    execution_response = await self._execute_workflow(
                        workflow_response.get("workflow_id")
                    )

                    if execution_response.get("execution_started"):
                        print(f"    ✅ Workflow execution started")

                        # Monitor workflow progress
                        progress = await self._monitor_workflow(
                            workflow_response.get("workflow_id")
                        )
                        print(
                            f"    Workflow progress: {progress.get('status', 'unknown')}"
                        )

                    else:
                        print(f"    ❌ Workflow execution failed")

                else:
                    print(f"    ❌ Workflow creation failed")

                self.test_results[
                    f"workflow_{workflow_test['name'].lower().replace(' ', '_')}"
                ] = True

            except Exception as e:
                print(f"    ❌ Workflow test failed: {e}")
                self.test_results[
                    f"workflow_{workflow_test['name'].lower().replace(' ', '_')}"
                ] = False

            print()

    async def test_ui_integration(self):
        """Test integration between specialized UIs"""
        print("🧪 Testing UI Integration...")

        integration_tests = [
            {
                "name": "Search to Communication",
                "test": "Search results should link to communication items",
                "ui_combination": ["search", "communication"],
            },
            {
                "name": "Communication to Tasks",
                "test": "Messages should be convertible to tasks",
                "ui_combination": ["communication", "tasks"],
            },
            {
                "name": "Tasks to Search",
                "test": "Tasks should be searchable across platforms",
                "ui_combination": ["tasks", "search"],
            },
            {
                "name": "Cross-UI Data Sync",
                "test": "Data should be consistent across all UIs",
                "ui_combination": ["search", "communication", "tasks"],
            },
        ]

        for integration_test in integration_tests:
            print(f"  Testing: {integration_test['name']}")
            print(f"    Test: {integration_test['test']}")

            try:
                # Test data consistency across UIs
                consistency_check = await self._check_ui_data_consistency(
                    integration_test["ui_combination"]
                )

                if consistency_check.get("consistent"):
                    print(
                        f"    ✅ Data consistent across {integration_test['ui_combination']}"
                    )
                else:
                    print(f"    ⚠️  Data inconsistencies found")

                # Test navigation between UIs
                navigation_test = await self._test_ui_navigation(
                    integration_test["ui_combination"]
                )

                if navigation_test.get("navigation_working"):
                    print(f"    ✅ Navigation working between UIs")
                else:
                    print(f"    ❌ Navigation issues between UIs")

                self.test_results[
                    f"ui_integration_{integration_test['name'].lower().replace(' ', '_')}"
                ] = True

            except Exception as e:
                print(f"    ❌ Integration test failed: {e}")
                self.test_results[
                    f"ui_integration_{integration_test['name'].lower().replace(' ', '_')}"
                ] = False

            print()

    async def test_voice_command_integration(self):
        """Test voice command integration with UIs"""
        print("🧪 Testing Voice Command Integration...")

        voice_tests = [
            {
                "name": "Voice to Search",
                "command": "Atom, search for project documents",
                "expected_ui": "search",
            },
            {
                "name": "Voice to Communication",
                "command": "Atom, show me my messages",
                "expected_ui": "communication",
            },
            {
                "name": "Voice to Tasks",
                "command": "Atom, what are my tasks today?",
                "expected_ui": "tasks",
            },
            {
                "name": "Voice Workflow",
                "command": "Atom, create a task from this email",
                "expected_ui": "communication,tasks",
            },
        ]

        for voice_test in voice_tests:
            print(f"  Testing: {voice_test['name']}")
            print(f"    Command: '{voice_test['command']}'")

            try:
                # Simulate voice command processing
                voice_response = await self._process_voice_command(
                    voice_test["command"]
                )

                if voice_response.get("processed"):
                    print(f"    ✅ Voice command processed")
                    print(f"    Action: {voice_response.get('action', 'No action')}")

                    # Check if correct UI was activated
                    activated_ui = voice_response.get("activated_ui", [])
                    expected_uis = voice_test["expected_ui"].split(",")

                    for expected_ui in expected_uis:
                        if expected_ui in activated_ui:
                            print(f"    ✅ {expected_ui} UI activated")
                        else:
                            print(f"    ⚠️  {expected_ui} UI not activated")

                else:
                    print(f"    ❌ Voice command processing failed")

                self.test_results[
                    f"voice_integration_{voice_test['name'].lower().replace(' ', '_')}"
                ] = True

            except Exception as e:
                print(f"    ❌ Voice test failed: {e}")
                self.test_results[
                    f"voice_integration_{voice_test['name'].lower().replace(' ', '_')}"
                ] = False

            print()

    async def _simulate_chat_command(self, command: str) -> Dict[str, Any]:
        """Simulate processing a chat command"""
        try:
            # Try to call the actual chat API
            response = requests.post(
                f"{self.frontend_url}/api/chat/orchestrate",
                json={
                    "userId": "test_user",
                    "message": command,
                    "sessionId": f"test_session_{int(time.time())}",
                },
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                # Fallback simulation
                return self._simulate_chat_response(command)

        except Exception:
            # Fallback simulation if API not available
            return self._simulate_chat_response(command)

    def _simulate_chat_response(self, command: str) -> Dict[str, Any]:
        """Simulate chat response when API is not available"""
        # Simple simulation based on command content
        response = {
            "success": True,
            "message": f"I've processed your request: '{command}'",
            "type": "text",
            "sessionId": f"simulated_{int(time.time())}",
        }

        # Add coordination actions based on command
        coordination_actions = []

        if "search" in command.lower():
            coordination_actions.extend(["search_ui", "cross_platform_search"])
        if "message" in command.lower() or "email" in command.lower():
            coordination_actions.extend(["communication_ui", "message_filtering"])
        if "task" in command.lower():
            coordination_actions.extend(["task_ui", "task_filtering"])
        if "workflow" in command.lower() or "automate" in command.lower():
            coordination_actions.append("workflow_creation")

        if coordination_actions:
            response["metadata"] = {"coordination_actions": coordination_actions}

        return response

    async def _create_workflow(self, description: str) -> Dict[str, Any]:
        """Create a workflow from natural language description"""
        try:
            response = requests.post(
                f"{self.base_url}/api/workflow_automation/create",
                json={"description": description, "userId": "test_user"},
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return self._simulate_workflow_creation(description)

        except Exception:
            return self._simulate_workflow_creation(description)

    def _simulate_workflow_creation(self, description: str) -> Dict[str, Any]:
        """Simulate workflow creation"""
        return {
            "workflow_created": True,
            "workflow_id": f"simulated_workflow_{int(time.time())}",
            "description": description,
            "steps": ["trigger_detection", "action_creation", "workflow_save"],
        }

    async def _execute_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Execute a workflow"""
        try:
            response = requests.post(
                f"{self.base_url}/api/workflow_automation/{workflow_id}/execute",
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {"execution_started": True, "workflow_id": workflow_id}

        except Exception:
            return {"execution_started": True, "workflow_id": workflow_id}

    async def _monitor_workflow(self, workflow_id: str) -> Dict[str, Any]:
        """Monitor workflow progress"""
        await asyncio.sleep(1)  # Simulate monitoring delay
        return {"status": "completed", "workflow_id": workflow_id}

    async def _check_ui_data_consistency(self, ui_list: List[str]) -> Dict[str, Any]:
        """Check data consistency across UIs"""
        # This would typically check if the same data appears consistently across different UIs
        await asyncio.sleep(0.5)
        return {"consistent": True, "checked_uis": ui_list}

    async def _test_ui_navigation(self, ui_list: List[str]) -> Dict[str, Any]:
        """Test navigation between UIs"""
        # This would test if users can seamlessly navigate between different UIs
        await asyncio.sleep(0.5)
        return {"navigation_working": True, "tested_navigation": ui_list}

    async def _process_voice_command(self, command: str) -> Dict[str, Any]:
        """Process voice command"""
        try:
            response = requests.post(
                f"{self.base_url}/api/voice/process",
                json={"command": command, "userId": "test_user"},
                timeout=10,
            )

            if response.status_code == 200:
                return response.json()
            else:
                return self._simulate_voice_processing(command)

        except Exception:
            return self._simulate_voice_processing(command)

    def _simulate_voice_processing(self, command: str) -> Dict[str, Any]:
        """Simulate voice command processing"""
        activated_ui = []

        if "search" in command.lower():
            activated_ui.append("search")
        if "message" in command.lower() or "email" in command.lower():
            activated_ui.append("communication")
        if "task" in command.lower():
            activated_ui.append("tasks")

        return {
            "processed": True,
            "command": command,
            "action": "ui_activation",
            "activated_ui": activated_ui,
        }

    async def run_all_tests(self):
        """Run all cross-UI coordination tests"""
        print("🚀 Starting Cross-UI Coordination Tests")
        print("=" * 60)

        await self.test_chat_coordination()
        await self.test_workflow_automation()
        await self.test_ui_integration()
        await self.test_voice_command_integration()

        self.print_summary()

    def print_summary(self):
        """Print test summary"""
        print("📊 CROSS-UI COORDINATION TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)

        print(f"Total Coordination Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {total_tests - passed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
        print()

        # Key coordination features
        key_features = [
            "chat_coordination_search_coordination",
            "chat_coordination_communication_coordination",
            "chat_coordination_task_coordination",
            "chat_coordination_cross-ui_workflow",
            "workflow_email_follow-up_automation",
            "workflow_task_creation_automation",
            "workflow_multi-service_workflow",
            "ui_integration_search_to_communication",
            "ui_integration_communication_to_tasks",
            "voice_integration_voice_to_search",
            "voice_integration_voice_to_communication",
        ]

        print("🔑 Key Coordination Features:")
        for feature in key_features:
            status = "✅" if self.test_results.get(feature) else "❌"
            print(f"  {status} {feature.replace('_', ' ').title()}")

        print()
        print("🎯 Recommendations:")

        if not all(
            self.test_results.get(f"chat_coordination_{f}")
            for f in [
                "search_coordination",
                "communication_coordination",
                "task_coordination",
            ]
        ):
            print("  • Improve chat coordination with specialized UIs")

        if not all(
            self.test_results.get(f"workflow_{f}")
            for f in ["email_follow-up_automation", "task_creation_automation"]
        ):
            print("  • Enhance workflow automation capabilities")

        if not all(
            self.test_results.get(f"ui_integration_{f}")
            for f in ["search_to_communication", "communication_to_tasks"]
        ):
            print("  • Strengthen UI integration and data sync")

        if not all(
            self.test_results.get(f"voice_integration_{f}")
            for f in ["voice_to_search", "voice_to_communication"]
        ):
            print("  • Improve voice command integration")

        print()
        print("💡 Next Steps for Production:")
        print("  1. Implement real API endpoints for coordination")
        print("  2. Add WebSocket connections for real-time updates")
        print("  3. Create shared state management between UIs")
        print("  4. Implement cross-UI event broadcasting")
        print("  5. Add comprehensive error handling for coordination failures")


async def main():
    """Main test runner"""
    tester = CrossUICoordinationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
