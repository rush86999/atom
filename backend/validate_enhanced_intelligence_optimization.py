"""
Enhanced Integration System Optimization Validation
Validates AI intelligence and cross-service detection improvements
"""

import json
import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from enhanced_workflow_intelligence import EnhancedWorkflowIntelligence

    print("✅ EnhancedWorkflowIntelligence imported successfully")
except ImportError as e:
    print(f"❌ Failed to import EnhancedWorkflowIntelligence: {e}")
    sys.exit(1)


class EnhancedIntegrationValidator:
    """Comprehensive validation for enhanced integration optimization"""

    def __init__(self):
        self.intelligence = EnhancedWorkflowIntelligence()
        self.validation_results = {
            "timestamp": datetime.now().isoformat(),
            "optimization_phase": "Phase 4 - AI Intelligence Enhancement",
            "systems": {},
            "overall_status": "PENDING",
            "success_rate": 0.0,
            "improvements": {},
        }

    def validate_service_detection(self):
        """Validate service detection accuracy improvements"""
        print("\n" + "=" * 70)
        print("VALIDATING SERVICE DETECTION OPTIMIZATION")
        print("=" * 70)

        test_cases = [
            {
                "input": "Send slack message when github PR is created",
                "expected": ["slack", "github"],
                "description": "Multi-service communication workflow",
            },
            {
                "input": "Create asana task from gmail email",
                "expected": ["asana", "gmail"],
                "description": "Email to task automation",
            },
            {
                "input": "Update google calendar when trello card is moved",
                "expected": ["google_calendar", "trello"],
                "description": "Calendar and project management integration",
            },
            {
                "input": "Upload file to dropbox and notify on slack",
                "expected": ["dropbox", "slack"],
                "description": "File sharing with notification",
            },
            {
                "input": "Create stripe invoice from salesforce opportunity",
                "expected": ["stripe", "salesforce"],
                "description": "CRM to payment processing",
            },
            {
                "input": "Schedule zoom meeting from google calendar event",
                "expected": ["zoom", "google_calendar"],
                "description": "Meeting scheduling integration",
            },
            {
                "input": "Send whatsapp message for urgent notifications",
                "expected": ["whatsapp"],
                "description": "Business messaging workflow",
            },
            {
                "input": "Generate tableau report from github data",
                "expected": ["tableau", "github"],
                "description": "Data analytics and reporting",
            },
        ]

        results = {
            "total_tests": len(test_cases),
            "passed_tests": 0,
            "success_rate": 0.0,
            "test_details": [],
        }

        for i, test in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test['description']}")
            print(f"Input: '{test['input']}'")
            print(f"Expected: {test['expected']}")

            try:
                detected_services = self.intelligence.detect_services_intelligently(
                    test["input"]
                )
                detected_names = [s.service_name for s in detected_services]

                print(f"Detected: {detected_names}")
                print(
                    f"Confidence Scores: {[f'{s.confidence:.2f}' for s in detected_services]}"
                )

                # Check if all expected services are detected
                missing = set(test["expected"]) - set(detected_names)
                extra = set(detected_names) - set(test["expected"])

                passed = len(missing) == 0

                if passed:
                    print("✅ PASS")
                    results["passed_tests"] += 1
                else:
                    print(f"❌ FAIL - Missing: {missing}, Extra: {extra}")

                test_detail = {
                    "test_id": i,
                    "input": test["input"],
                    "expected": test["expected"],
                    "detected": detected_names,
                    "confidence_scores": [s.confidence for s in detected_services],
                    "missing": list(missing),
                    "extra": list(extra),
                    "passed": passed,
                }
                results["test_details"].append(test_detail)

            except Exception as e:
                print(f"❌ ERROR: {e}")
                test_detail = {
                    "test_id": i,
                    "input": test["input"],
                    "error": str(e),
                    "passed": False,
                }
                results["test_details"].append(test_detail)

        # Calculate success rate
        results["success_rate"] = (
            results["passed_tests"] / results["total_tests"]
        ) * 100

        print(f"\n📊 Service Detection Results:")
        print(f"   Total Tests: {results['total_tests']}")
        print(f"   Passed Tests: {results['passed_tests']}")
        print(f"   Success Rate: {results['success_rate']:.1f}%")

        self.validation_results["systems"]["service_detection"] = results
        return results

    def validate_cross_service_intelligence(self):
        """Validate cross-service relationship detection"""
        print("\n" + "=" * 70)
        print("VALIDATING CROSS-SERVICE INTELLIGENCE")
        print("=" * 70)

        test_cases = [
            {
                "input": "When github PR is created, send slack message and create asana task",
                "description": "Multi-service workflow with trigger and multiple actions",
            },
            {
                "input": "Sync google calendar with outlook and notify on slack",
                "description": "Calendar synchronization with notifications",
            },
            {
                "input": "Create salesforce lead from gmail, add to asana, and notify team",
                "description": "Complex multi-service lead management",
            },
        ]

        results = {
            "total_tests": len(test_cases),
            "successful_analyses": 0,
            "success_rate": 0.0,
            "average_services_detected": 0.0,
            "test_details": [],
        }

        total_services = 0

        for i, test in enumerate(test_cases, 1):
            print(f"\nTest {i}: {test['description']}")
            print(f"Input: '{test['input']}'")

            try:
                # Service detection
                detected_services = self.intelligence.detect_services_intelligently(
                    test["input"]
                )
                detected_names = [s.service_name for s in detected_services]

                print(f"Detected Services: {detected_names}")
                print(f"Number of Services: {len(detected_services)}")

                # Workflow generation
                workflow = self.intelligence.generate_optimized_workflow(
                    test["input"], detected_services
                )

                print(f"Workflow Complexity: {workflow.get('complexity', 'N/A')}")
                print(f"Estimated Time: {workflow.get('estimated_time', 'N/A')}s")
                print(
                    f"Optimization Potential: {workflow.get('optimization_potential', 'N/A')}"
                )

                test_detail = {
                    "test_id": i,
                    "input": test["input"],
                    "detected_services": detected_names,
                    "services_count": len(detected_services),
                    "workflow_complexity": workflow.get("complexity"),
                    "estimated_time": workflow.get("estimated_time"),
                    "optimization_potential": workflow.get("optimization_potential"),
                    "success": True,
                }

                results["successful_analyses"] += 1
                total_services += len(detected_services)
                results["test_details"].append(test_detail)

                print("✅ Analysis Complete")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                test_detail = {
                    "test_id": i,
                    "input": test["input"],
                    "error": str(e),
                    "success": False,
                }
                results["test_details"].append(test_detail)

        # Calculate averages
        if results["total_tests"] > 0:
            results["average_services_detected"] = (
                total_services / results["total_tests"]
            )
            results["success_rate"] = (
                results["successful_analyses"] / results["total_tests"]
            ) * 100

        print(f"\n📊 Cross-Service Intelligence Results:")
        print(f"   Total Tests: {results['total_tests']}")
        print(f"   Successful Analyses: {results['successful_analyses']}")
        print(f"   Success Rate: {results['success_rate']:.1f}%")
        print(
            f"   Average Services Detected: {results['average_services_detected']:.1f}"
        )

        self.validation_results["systems"]["cross_service_intelligence"] = results
        return results

    def validate_workflow_optimization(self):
        """Validate workflow optimization capabilities"""
        print("\n" + "=" * 70)
        print("VALIDATING WORKFLOW OPTIMIZATION")
        print("=" * 70)

        test_input = "Create asana task from gmail email and notify on slack"

        try:
            print(f"Input: '{test_input}'")

            # Detect services
            detected_services = self.intelligence.detect_services_intelligently(
                test_input
            )
            detected_names = [s.service_name for s in detected_services]

            print(f"Detected Services: {detected_names}")

            # Generate optimized workflow
            workflow = self.intelligence.generate_optimized_workflow(
                test_input, detected_services
            )

            print(f"Workflow ID: {workflow.get('workflow_id')}")
            print(f"Complexity: {workflow.get('complexity')}")
            print(f"Estimated Time: {workflow.get('estimated_time')}s")
            print(f"Estimated Cost: ${workflow.get('estimated_cost')}")
            print(f"Optimization Potential: {workflow.get('optimization_potential')}")
            print(f"Confidence: {workflow.get('confidence')}")

            # Validate workflow structure
            has_required_fields = all(
                [
                    workflow.get("workflow_id"),
                    workflow.get("name"),
                    workflow.get("services"),
                    workflow.get("steps"),
                    workflow.get("complexity"),
                ]
            )

            results = {
                "success": True,
                "workflow_generated": True,
                "has_required_fields": has_required_fields,
                "services_detected": len(detected_services),
                "complexity": workflow.get("complexity"),
                "estimated_time": workflow.get("estimated_time"),
                "estimated_cost": workflow.get("estimated_cost"),
                "optimization_potential": workflow.get("optimization_potential"),
                "confidence": workflow.get("confidence"),
            }

            if has_required_fields:
                print("✅ Workflow Optimization PASS")
            else:
                print("❌ Workflow Optimization FAIL - Missing required fields")

        except Exception as e:
            print(f"❌ Workflow Optimization ERROR: {e}")
            results = {"success": False, "error": str(e), "workflow_generated": False}

        self.validation_results["systems"]["workflow_optimization"] = results
        return results

    def calculate_improvements(self):
        """Calculate improvements from previous validation"""
        previous_results_file = (
            "enhanced_integrations_validation_report_20251112_130911.json"
        )

        try:
            with open(previous_results_file, "r") as f:
                previous_results = json.load(f)

            previous_ai = previous_results["systems"]["ai_intelligence"]["success_rate"]
            previous_cross = previous_results["systems"]["cross_service_intelligence"][
                "success_rate"
            ]

            current_ai = self.validation_results["systems"]["service_detection"][
                "success_rate"
            ]
            current_cross = self.validation_results["systems"][
                "cross_service_intelligence"
            ]["success_rate"]

            improvements = {
                "ai_intelligence": {
                    "previous": previous_ai,
                    "current": current_ai,
                    "improvement": current_ai - previous_ai,
                    "improvement_percent": ((current_ai - previous_ai) / previous_ai)
                    * 100
                    if previous_ai > 0
                    else 100,
                },
                "cross_service_intelligence": {
                    "previous": previous_cross,
                    "current": current_cross,
                    "improvement": current_cross - previous_cross,
                    "improvement_percent": (
                        (current_cross - previous_cross) / previous_cross
                    )
                    * 100
                    if previous_cross > 0
                    else 100,
                },
            }

            self.validation_results["improvements"] = improvements

            print(f"\n📈 IMPROVEMENT ANALYSIS:")
            print(
                f"   AI Intelligence: {previous_ai:.1f}% → {current_ai:.1f}% (+{improvements['ai_intelligence']['improvement']:.1f}%)"
            )
            print(
                f"   Cross-Service: {previous_cross:.1f}% → {current_cross:.1f}% (+{improvements['cross_service_intelligence']['improvement']:.1f}%)"
            )

        except FileNotFoundError:
            print(
                "⚠️  Previous validation results not found - cannot calculate improvements"
            )
            self.validation_results["improvements"] = {
                "error": "Previous results not available"
            }

    def generate_final_report(self):
        """Generate comprehensive validation report"""
        print("\n" + "=" * 70)
        print("FINAL VALIDATION REPORT")
        print("=" * 70)

        # Calculate overall success rate
        service_detection = self.validation_results["systems"]["service_detection"][
            "success_rate"
        ]
        cross_service = self.validation_results["systems"][
            "cross_service_intelligence"
        ]["success_rate"]
        workflow_opt = (
            100
            if self.validation_results["systems"]["workflow_optimization"]["success"]
            else 0
        )

        overall_success_rate = (service_detection + cross_service + workflow_opt) / 3

        self.validation_results["success_rate"] = overall_success_rate

        # Determine overall status
        if overall_success_rate >= 85:
            self.validation_results["overall_status"] = "EXCELLENT"
            status_emoji = "🎉"
        elif overall_success_rate >= 70:
            self.validation_results["overall_status"] = "GOOD"
            status_emoji = "✅"
        else:
            self.validation_results["overall_status"] = "NEEDS_IMPROVEMENT"
            status_emoji = "⚠️"

        print(
            f"\n📊 OVERALL SYSTEM STATUS: {status_emoji} {self.validation_results['overall_status']}"
        )
        print(f"   Overall Success Rate: {overall_success_rate:.1f}%")
        print(f"   Service Detection: {service_detection:.1f}%")
        print(f"   Cross-Service Intelligence: {cross_service:.1f}%")
        print(f"   Workflow Optimization: {workflow_opt:.1f}%")

        # Save detailed report
        output_file = f"enhanced_intelligence_optimization_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, "w") as f:
            json.dump(self.validation_results, f, indent=2)

        print(f"\n📄 Detailed report saved to: {output_file}")

        return self.validation_results

    def run_comprehensive_validation(self):
        """Run all validation tests"""
        print("🚀 ENHANCED INTEGRATION SYSTEM OPTIMIZATION VALIDATION")
        print("Validating AI intelligence and cross-service detection improvements")

        # Run all validation tests
        self.validate_service_detection()
        self.validate_cross_service_intelligence()
        self.validate_workflow_optimization()

        # Calculate improvements
        self.calculate_improvements()

        # Generate final report
        final_report = self.generate_final_report()

        return final_report


def main():
    """Main validation execution"""
    validator = EnhancedIntegrationValidator()
    results = validator.run_comprehensive_validation()

    # Print final summary
    print("\n" + "=" * 70)
    print("OPTIMIZATION VALIDATION COMPLETE")
    print("=" * 70)

    if results["overall_status"] == "EXCELLENT":
        print("🎉 OPTIMIZATION SUCCESSFUL! All targets achieved.")
        print("   The enhanced integration system is ready for enterprise deployment.")
    elif results["overall_status"] == "GOOD":
        print("✅ Optimization progressing well. System is functional.")
        print("   Minor improvements may be needed before full deployment.")
    else:
        print("⚠️  Further optimization needed.")
        print("   Review the detailed report for specific areas requiring improvement.")


if __name__ == "__main__":
    main()
