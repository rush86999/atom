"""
Test script for AI Intelligence Optimization
Validates service detection improvements and cross-service intelligence
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


def test_service_detection():
    """Test service detection with various input patterns"""
    print("\n" + "=" * 60)
    print("TESTING SERVICE DETECTION OPTIMIZATION")
    print("=" * 60)

    intelligence = EnhancedWorkflowIntelligence()

    test_cases = [
        {
            "input": "Send slack message when github PR is created",
            "expected_services": ["slack", "github"],
            "description": "Multi-service workflow with communication and code",
        },
        {
            "input": "Create asana task from gmail email",
            "expected_services": ["asana", "gmail"],
            "description": "Email to task automation workflow",
        },
        {
            "input": "Update google calendar when trello card is moved",
            "expected_services": ["google_calendar", "trello"],
            "description": "Calendar and project management integration",
        },
        {
            "input": "Upload file to dropbox and notify on slack",
            "expected_services": ["dropbox", "slack"],
            "description": "File sharing with notification",
        },
        {
            "input": "Create stripe invoice from salesforce opportunity",
            "expected_services": ["stripe", "salesforce"],
            "description": "CRM to payment processing workflow",
        },
        {
            "input": "Schedule zoom meeting from google calendar event",
            "expected_services": ["zoom", "google_calendar"],
            "description": "Meeting scheduling integration",
        },
        {
            "input": "Send whatsapp message for urgent notifications",
            "expected_services": ["whatsapp"],
            "description": "Business messaging workflow",
        },
        {
            "input": "Generate tableau report from github data",
            "expected_services": ["tableau", "github"],
            "description": "Data analytics and reporting workflow",
        },
    ]

    results = {
        "timestamp": datetime.now().isoformat(),
        "test_cases": [],
        "summary": {
            "total_tests": len(test_cases),
            "passed_tests": 0,
            "success_rate": 0.0,
        },
    }

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print(f"Input: '{test_case['input']}'")
        print(f"Expected: {test_case['expected_services']}")

        try:
            detected_services = intelligence.detect_services_intelligently(
                test_case["input"]
            )
            detected_names = [service.service_name for service in detected_services]

            print(f"Detected: {detected_names}")
            print(
                f"Confidence Scores: {[f'{s.confidence:.2f}' for s in detected_services]}"
            )

            # Check if all expected services were detected
            missing_services = set(test_case["expected_services"]) - set(detected_names)
            extra_services = set(detected_names) - set(test_case["expected_services"])

            passed = len(missing_services) == 0

            if passed:
                print("✅ PASS")
                results["summary"]["passed_tests"] += 1
            else:
                print(f"❌ FAIL - Missing: {missing_services}, Extra: {extra_services}")

            test_result = {
                "test_id": i,
                "input": test_case["input"],
                "expected_services": test_case["expected_services"],
                "detected_services": detected_names,
                "confidence_scores": [s.confidence for s in detected_services],
                "missing_services": list(missing_services),
                "extra_services": list(extra_services),
                "passed": passed,
                "details": {
                    "detected_services_full": [
                        {
                            "service_name": s.service_name,
                            "confidence": s.confidence,
                            "detected_keywords": s.detected_keywords,
                            "suggested_actions": s.suggested_actions,
                        }
                        for s in detected_services
                    ]
                },
            }

            results["test_cases"].append(test_result)

        except Exception as e:
            print(f"❌ ERROR: {e}")
            test_result = {
                "test_id": i,
                "input": test_case["input"],
                "error": str(e),
                "passed": False,
            }
            results["test_cases"].append(test_result)

    # Calculate success rate
    results["summary"]["success_rate"] = (
        results["summary"]["passed_tests"] / results["summary"]["total_tests"]
    ) * 100

    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results['summary']['total_tests']}")
    print(f"Passed Tests: {results['summary']['passed_tests']}")
    print(f"Success Rate: {results['summary']['success_rate']:.1f}%")

    return results


def test_cross_service_intelligence():
    """Test cross-service relationship detection and optimization"""
    print("\n" + "=" * 60)
    print("TESTING CROSS-SERVICE INTELLIGENCE")
    print("=" * 60)

    intelligence = EnhancedWorkflowIntelligence()

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
        "timestamp": datetime.now().isoformat(),
        "test_cases": [],
        "summary": {
            "total_tests": len(test_cases),
            "successful_analyses": 0,
            "average_services_detected": 0,
        },
    }

    total_services_detected = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}: {test_case['description']}")
        print(f"Input: '{test_case['input']}'")

        try:
            detected_services = intelligence.detect_services_intelligently(
                test_case["input"]
            )
            detected_names = [service.service_name for service in detected_services]

            print(f"Detected Services: {detected_names}")
            print(f"Number of Services: {len(detected_services)}")

            # Test workflow generation
            try:
                optimized_workflow = intelligence.generate_optimized_workflow(
                    test_case["input"], detected_services
                )
                print(
                    f"Workflow Complexity: {optimized_workflow.get('complexity', 'N/A')}"
                )
                print(
                    f"Estimated Time: {optimized_workflow.get('estimated_time', 'N/A')}s"
                )
                print(
                    f"Optimization Potential: {optimized_workflow.get('optimization_potential', 'N/A')}"
                )

                workflow_success = True
            except Exception as e:
                print(f"Workflow generation failed: {e}")
                workflow_success = False

            test_result = {
                "test_id": i,
                "input": test_case["input"],
                "detected_services": detected_names,
                "services_count": len(detected_services),
                "workflow_generation_success": workflow_success,
                "details": {
                    "detected_services_full": [
                        {
                            "service_name": s.service_name,
                            "confidence": s.confidence,
                            "context": s.context,
                        }
                        for s in detected_services
                    ]
                },
            }

            if workflow_success:
                results["summary"]["successful_analyses"] += 1

            total_services_detected += len(detected_services)
            results["test_cases"].append(test_result)

            print("✅ Analysis Complete")

        except Exception as e:
            print(f"❌ ERROR: {e}")
            test_result = {
                "test_id": i,
                "input": test_case["input"],
                "error": str(e),
                "workflow_generation_success": False,
            }
            results["test_cases"].append(test_result)

    # Calculate averages
    if results["summary"]["total_tests"] > 0:
        results["summary"]["average_services_detected"] = (
            total_services_detected / results["summary"]["total_tests"]
        )

    print("\n" + "=" * 60)
    print("CROSS-SERVICE INTELLIGENCE SUMMARY")
    print("=" * 60)
    print(f"Total Tests: {results['summary']['total_tests']}")
    print(f"Successful Analyses: {results['summary']['successful_analyses']}")
    print(
        f"Average Services Detected: {results['summary']['average_services_detected']:.1f}"
    )

    return results


def main():
    """Run comprehensive optimization tests"""
    print("🚀 ATOM AI INTELLIGENCE OPTIMIZATION TEST")
    print("Testing service detection and cross-service intelligence improvements")

    # Test service detection
    service_results = test_service_detection()

    # Test cross-service intelligence
    cross_service_results = test_cross_service_intelligence()

    # Generate comprehensive report
    final_report = {
        "timestamp": datetime.now().isoformat(),
        "service_detection": service_results,
        "cross_service_intelligence": cross_service_results,
        "overall_assessment": {
            "service_detection_success_rate": service_results["summary"][
                "success_rate"
            ],
            "cross_service_success_rate": (
                cross_service_results["summary"]["successful_analyses"]
                / cross_service_results["summary"]["total_tests"]
            )
            * 100
            if cross_service_results["summary"]["total_tests"] > 0
            else 0,
            "improvement_status": "PENDING",  # Will be updated based on results
        },
    }

    # Save detailed results
    output_file = "ai_intelligence_optimization_results.json"
    with open(output_file, "w") as f:
        json.dump(final_report, f, indent=2)

    print(f"\n📊 Detailed results saved to: {output_file}")

    # Overall assessment
    service_rate = final_report["overall_assessment"]["service_detection_success_rate"]
    cross_service_rate = final_report["overall_assessment"][
        "cross_service_success_rate"
    ]

    print("\n" + "=" * 60)
    print("OVERALL OPTIMIZATION ASSESSMENT")
    print("=" * 60)
    print(f"Service Detection Success Rate: {service_rate:.1f}%")
    print(f"Cross-Service Intelligence Rate: {cross_service_rate:.1f}%")

    if service_rate >= 85 and cross_service_rate >= 90:
        final_report["overall_assessment"]["improvement_status"] = "EXCELLENT"
        print("🎉 OPTIMIZATION SUCCESSFUL - Targets Achieved!")
    elif service_rate >= 75 and cross_service_rate >= 80:
        final_report["overall_assessment"]["improvement_status"] = "GOOD"
        print("✅ Optimization Progressing Well - Close to Targets")
    else:
        final_report["overall_assessment"]["improvement_status"] = "NEEDS_IMPROVEMENT"
        print("⚠️  Further Optimization Needed")

    # Update the saved report with final assessment
    with open(output_file, "w") as f:
        json.dump(final_report, f, indent=2)

    return final_report


if __name__ == "__main__":
    results = main()
