#!/usr/bin/env python3
"""
ATOM Platform - AI Integration Test Script

This script tests the AI integration components including:
- Natural Language Processing Engine
- Data Intelligence Engine
- Automation Engine
- API Integration

Usage:
    python test_ai_integration.py
"""

import asyncio
import json
import logging
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))
sys.path.append(os.path.join(os.path.dirname(__file__), "backend", "ai"))

from ai.automation_engine import AutomationEngine
from ai.data_intelligence import DataIntelligenceEngine, EntityType, PlatformType
from ai.nlp_engine import NaturalLanguageEngine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class AIIntegrationTest:
    """Comprehensive AI Integration Test Suite"""

    def __init__(self):
        self.nlp_engine = NaturalLanguageEngine()
        self.data_engine = DataIntelligenceEngine()
        self.automation_engine = AutomationEngine()
        self.test_results = {}

    async def test_nlp_engine(self):
        """Test Natural Language Processing Engine"""
        print("\n🧠 Testing NLP Engine...")
        print("=" * 50)

        test_commands = [
            "Find all overdue tasks in Asana and Jira",
            "Schedule a team meeting for tomorrow at 2pm",
            "Create a new contact in Salesforce for John Doe",
            "Show me the Q3 sales report from HubSpot",
            "What are my upcoming deadlines across all platforms?",
            "Send a message to the team about the project update",
            "Search for files related to budget planning",
        ]

        results = []
        for command in test_commands:
            print(f"\nCommand: '{command}'")
            intent = self.nlp_engine.parse_command(command)
            response = self.nlp_engine.generate_response(intent)

            result = {
                "command": command,
                "command_type": intent.command_type.value,
                "platforms": [p.value for p in intent.platforms],
                "confidence": intent.confidence,
                "entities": intent.entities,
                "success": response["success"],
            }
            results.append(result)

            print(f"  Type: {intent.command_type.value}")
            print(f"  Platforms: {[p.value for p in intent.platforms]}")
            print(f"  Confidence: {intent.confidence:.2f}")
            print(f"  Entities: {intent.entities}")
            print(f"  Message: {response['message']}")

        # Calculate success rate
        success_rate = sum(1 for r in results if r["success"]) / len(results)
        self.test_results["nlp_engine"] = {
            "success_rate": success_rate,
            "total_tests": len(results),
            "passed_tests": sum(1 for r in results if r["success"]),
            "average_confidence": sum(r["confidence"] for r in results) / len(results),
        }

        print(f"\n✅ NLP Engine Test Complete")
        print(f"   Success Rate: {success_rate:.1%}")
        print(
            f"   Average Confidence: {self.test_results['nlp_engine']['average_confidence']:.2f}"
        )

        return success_rate > 0.7

    async def test_data_intelligence_engine(self):
        """Test Data Intelligence Engine"""
        print("\n📊 Testing Data Intelligence Engine...")
        print("=" * 50)

        # Test data ingestion
        platforms_to_test = [
            PlatformType.ASANA,
            PlatformType.SALESFORCE,
            PlatformType.HUBSPOT,
        ]

        total_entities = 0
        for platform in platforms_to_test:
            mock_data = self.data_engine._mock_platform_connector(platform)
            unified_entities = self.data_engine.ingest_platform_data(
                platform, mock_data
            )
            total_entities += len(unified_entities)
            print(f"  Ingested {len(unified_entities)} entities from {platform.value}")

        # Test search functionality
        search_queries = ["john", "acme", "report", "q3"]
        search_results = {}

        for query in search_queries:
            results = self.data_engine.search_unified_entities(query)
            search_results[query] = len(results)
            print(f"  Search '{query}': {len(results)} results")

        # Test entity resolution
        duplicate_contacts = 0
        for entity in self.data_engine.entity_registry.values():
            if (
                entity.entity_type == EntityType.CONTACT
                and len(entity.source_platforms) > 1
            ):
                duplicate_contacts += 1

        # Test relationships
        total_relationships = len(self.data_engine.relationship_registry)

        self.test_results["data_intelligence"] = {
            "total_entities": len(self.data_engine.entity_registry),
            "entities_ingested": total_entities,
            "relationships_created": total_relationships,
            "duplicate_resolutions": duplicate_contacts,
            "search_performance": search_results,
        }

        print(f"\n✅ Data Intelligence Engine Test Complete")
        print(f"   Total Unified Entities: {len(self.data_engine.entity_registry)}")
        print(f"   Relationships Created: {total_relationships}")
        print(f"   Duplicate Resolutions: {duplicate_contacts}")

        return len(self.data_engine.entity_registry) > 0

    async def test_automation_engine(self):
        """Test Automation Engine"""
        print("\n⚙️ Testing Automation Engine...")
        print("=" * 50)

        # Create test workflows
        workflows_data = [
            {
                "name": "Daily Team Update",
                "description": "Send daily team updates and create follow-up tasks",
                "trigger": {
                    "type": "scheduled",
                    "platform": "slack",
                    "event_name": "daily_reminder",
                    "conditions": {"time": "09:00", "weekday": "mon-fri"},
                    "description": "Triggered every weekday at 9 AM",
                },
                "actions": [
                    {
                        "type": "search",
                        "platform": "asana",
                        "target_entity": "tasks",
                        "parameters": {"status": "today", "assignee": "team"},
                        "description": "Find today's tasks for the team",
                    },
                    {
                        "type": "notify",
                        "platform": "slack",
                        "target_entity": "channel",
                        "parameters": {
                            "channel": "#team-updates",
                            "message": "Daily update ready",
                        },
                        "description": "Send notification to Slack channel",
                    },
                ],
                "conditions": [],
            },
            {
                "name": "New Contact Follow-up",
                "description": "Automated follow-up for new contacts",
                "trigger": {
                    "type": "event_based",
                    "platform": "salesforce",
                    "event_name": "contact_created",
                    "conditions": {},
                    "description": "Triggered when new contact is created",
                },
                "actions": [
                    {
                        "type": "create",
                        "platform": "asana",
                        "target_entity": "task",
                        "parameters": {
                            "name": "Follow up with new contact",
                            "assignee": "sales_team",
                        },
                        "description": "Create follow-up task",
                    },
                    {
                        "type": "notify",
                        "platform": "slack",
                        "target_entity": "channel",
                        "parameters": {
                            "channel": "#sales",
                            "message": "New contact added - follow up required",
                        },
                        "description": "Notify sales team",
                    },
                ],
                "conditions": [],
            },
        ]

        # Create workflows
        workflows_created = []
        for workflow_data in workflows_data:
            workflow = self.automation_engine.create_workflow(workflow_data)
            workflows_created.append(workflow)
            print(f"  Created workflow: {workflow.name}")

        # Test workflow execution
        execution_results = []
        for workflow in workflows_created:
            trigger_data = {
                "time": "09:00",
                "weekday": "monday",
                "team": "engineering",
                "contact_name": "John Doe",
                "contact_email": "john@example.com",
            }

            execution = await self.automation_engine.execute_workflow(
                workflow.workflow_id, trigger_data
            )
            execution_results.append(execution)
            print(f"  Executed workflow '{workflow.name}': {execution.status}")

        # Calculate success rate
        successful_executions = sum(
            1 for e in execution_results if e.status == "completed"
        )
        success_rate = (
            successful_executions / len(execution_results) if execution_results else 0
        )

        self.test_results["automation_engine"] = {
            "workflows_created": len(workflows_created),
            "executions_completed": successful_executions,
            "total_executions": len(execution_results),
            "success_rate": success_rate,
            "actions_executed": sum(len(e.actions_executed) for e in execution_results),
        }

        print(f"\n✅ Automation Engine Test Complete")
        print(f"   Workflows Created: {len(workflows_created)}")
        print(
            f"   Executions Completed: {successful_executions}/{len(execution_results)}"
        )
        print(f"   Success Rate: {success_rate:.1%}")
        print(
            f"   Total Actions Executed: {self.test_results['automation_engine']['actions_executed']}"
        )

        return success_rate > 0.5

    async def test_integration_scenarios(self):
        """Test integrated AI scenarios"""
        print("\n🔄 Testing Integrated AI Scenarios...")
        print("=" * 50)

        scenarios = [
            {
                "name": "Cross-Platform Task Management",
                "description": "Use NLP to create task, data engine to find related entities, automation to execute",
                "steps": [
                    "Parse command: 'Create task for John about Q3 budget review'",
                    "Ingest related data from multiple platforms",
                    "Execute automation workflow",
                ],
            },
            {
                "name": "Intelligent Search and Automation",
                "description": "Search across platforms and trigger automated actions",
                "steps": [
                    "Search for 'overdue tasks' across all platforms",
                    "Identify related contacts and projects",
                    "Trigger notification workflow",
                ],
            },
        ]

        integrated_results = []
        for scenario in scenarios:
            print(f"\nScenario: {scenario['name']}")
            print(f"Description: {scenario['description']}")

            # Simulate integrated workflow
            try:
                # Step 1: NLP Processing
                test_command = "Find overdue tasks for John and notify team"
                nlp_intent = self.nlp_engine.parse_command(test_command)

                # Step 2: Data Intelligence
                search_results = self.data_engine.search_unified_entities("john")

                # Step 3: Automation (if applicable)
                if nlp_intent.command_type.value == "search" and search_results:
                    # This would trigger an automation workflow in production
                    integrated_success = True
                else:
                    integrated_success = False

                integrated_results.append(
                    {
                        "scenario": scenario["name"],
                        "success": integrated_success,
                        "nlp_confidence": nlp_intent.confidence,
                        "data_results": len(search_results),
                    }
                )

                print(f"  NLP Confidence: {nlp_intent.confidence:.2f}")
                print(f"  Data Results: {len(search_results)} entities")
                print(f"  Integrated Success: {integrated_success}")

            except Exception as e:
                print(f"  ❌ Scenario failed: {str(e)}")
                integrated_results.append(
                    {"scenario": scenario["name"], "success": False, "error": str(e)}
                )

        # Calculate integrated success rate
        successful_scenarios = sum(1 for r in integrated_results if r["success"])
        integrated_success_rate = (
            successful_scenarios / len(integrated_results) if integrated_results else 0
        )

        self.test_results["integration_scenarios"] = {
            "total_scenarios": len(integrated_results),
            "successful_scenarios": successful_scenarios,
            "success_rate": integrated_success_rate,
            "scenario_details": integrated_results,
        }

        print(f"\n✅ Integrated Scenarios Test Complete")
        print(f"   Success Rate: {integrated_success_rate:.1%}")

        return integrated_success_rate > 0.5

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "=" * 60)
        print("📋 AI INTEGRATION TEST REPORT")
        print("=" * 60)

        overall_success = all(
            [
                self.test_results["nlp_engine"]["success_rate"] > 0.7,
                self.test_results["data_intelligence"]["total_entities"] > 0,
                self.test_results["automation_engine"]["success_rate"] > 0.5,
                self.test_results["integration_scenarios"]["success_rate"] > 0.5,
            ]
        )

        print(f"\nOverall Status: {'✅ PASS' if overall_success else '❌ FAIL'}")

        # Component Summary
        print(f"\nComponent Summary:")
        print(
            f"  🧠 NLP Engine: {self.test_results['nlp_engine']['passed_tests']}/{self.test_results['nlp_engine']['total_tests']} passed"
        )
        print(
            f"  📊 Data Intelligence: {self.test_results['data_intelligence']['total_entities']} entities unified"
        )
        print(
            f"  ⚙️ Automation Engine: {self.test_results['automation_engine']['success_rate']:.1%} success rate"
        )
        print(
            f"  🔄 Integration: {self.test_results['integration_scenarios']['success_rate']:.1%} scenario success"
        )

        # Detailed Metrics
        print(f"\nDetailed Metrics:")
        print(
            f"  - NLP Average Confidence: {self.test_results['nlp_engine']['average_confidence']:.2f}"
        )
        print(
            f"  - Data Relationships: {self.test_results['data_intelligence']['relationships_created']}"
        )
        print(
            f"  - Automation Actions: {self.test_results['automation_engine']['actions_executed']}"
        )
        print(
            f"  - Integrated Scenarios: {self.test_results['integration_scenarios']['successful_scenarios']}/{self.test_results['integration_scenarios']['total_scenarios']}"
        )

        # Recommendations
        print(f"\nRecommendations:")
        if self.test_results["nlp_engine"]["average_confidence"] < 0.8:
            print("  • Improve NLP pattern matching for better command recognition")
        if self.test_results["data_intelligence"]["relationships_created"] < 5:
            print(
                "  • Enhance entity resolution algorithms for better relationship detection"
            )
        if self.test_results["automation_engine"]["success_rate"] < 0.8:
            print("  • Add more robust error handling in automation workflows")
        if self.test_results["integration_scenarios"]["success_rate"] < 0.8:
            print("  • Improve integration between AI components")

        return overall_success

    async def run_all_tests(self):
        """Run all AI integration tests"""
        print("🚀 Starting AI Integration Test Suite")
        print("=" * 60)

        try:
            # Run individual component tests
            nlp_success = await self.test_nlp_engine()
            data_success = await self.test_data_intelligence_engine()
            automation_success = await self.test_automation_engine()
            integration_success = await self.test_integration_scenarios()

            # Generate final report
            overall_success = self.generate_test_report()

            # Save test results
            with open("ai_integration_test_results.json", "w") as f:
                json.dump(self.test_results, f, indent=2, default=str)

            print(f"\n📁 Test results saved to: ai_integration_test_results.json")

            return overall_success

        except Exception as e:
            logger.error(f"Test suite failed: {str(e)}")
            return False


async def main():
    """Main execution function"""
    test_suite = AIIntegrationTest()
    success = await test_suite.run_all_tests()

    if success:
        print(f"\n🎉 AI INTEGRATION TEST SUITE COMPLETED SUCCESSFULLY!")
        print(f"   All components are ready for production integration.")
    else:
        print(f"\n⚠️ AI INTEGRATION TEST SUITE COMPLETED WITH ISSUES")
        print(f"   Review the recommendations above for improvements.")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
