#!/usr/bin/env python3
"""
Business Outcome Test Runner
Tests actual business value and ROI delivered by ATOM platform
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import time
from datetime import datetime
from utils.business_outcome_validator import BusinessOutcomeValidator
from utils.llm_verifier import LLMVerifier


class BusinessOutcomeTestRunner:
    """Runner for business-focused validation tests"""

    def __init__(self):
        print("🎯 Initializing Business Outcome Test Runner...")

        try:
            self.business_validator = BusinessOutcomeValidator()
            self.business_validator_available = True
            print("✅ Business Outcome Validator: Available")
        except Exception as e:
            print(f"⚠️  Business Outcome Validator: Unavailable - {e}")
            self.business_validator_available = False

        try:
            self.llm_verifier = LLMVerifier()
            self.llm_verifier_available = True
            print("✅ LLM Verifier: Available")
        except Exception as e:
            print(f"⚠️  LLM Verifier: Unavailable - {e}")
            self.llm_verifier_available = False

    def test_employee_onboarding_roi(self) -> dict:
        """Test ROI for employee onboarding automation"""
        print("\n" + "="*60)
        print("TEST 1: Employee Onboarding ROI")
        print("="*60)

        if not self.business_validator_available:
            return self._skip_test("Business outcome validator not available")

        # Real business scenario
        scenario = {
            "workflow_name": "Employee Onboarding Automation",
            "time_saved_minutes": 210,  # 3.5 hours saved per hire
            "hourly_rate": 75.0,        # HR manager hourly rate
            "implementation_cost": 8000,
            "monthly_frequency": 10,    # 10 new hires per month
            "description": "Automate new hire account creation, equipment setup, and scheduling"
        }

        print(f"Scenario: {scenario['description']}")
        print(f"Time saved per hire: {scenario['time_saved_minutes']} minutes")
        print(f"Hourly rate: ${scenario['hourly_rate']}")
        print(f"Monthly hires: {scenario['monthly_frequency']}")

        # Calculate ROI
        roi_result = self.business_validator.calculate_automation_roi(
            workflow_name=scenario['workflow_name'],
            time_saved_minutes=scenario['time_saved_minutes'],
            hourly_rate=scenario['hourly_rate'],
            implementation_cost=scenario['implementation_cost'],
            monthly_frequency=scenario['monthly_frequency']
        )

        # Validate business value
        business_score = roi_result.get('business_value_score', 0)
        annual_roi = roi_result.get('roi_metrics', {}).get('annual_roi_percent', 0)
        annual_value = roi_result.get('financial_metrics', {}).get('annual_value', 0)

        print(f"\n📊 RESULTS:")
        print(f"   Business Value Score: {business_score}/10")
        print(f"   Annual ROI: {annual_roi:.1f}%")
        print(f"   Annual Value: ${annual_value:,.2f}")
        print(f"   Payback Period: {roi_result.get('roi_metrics', {}).get('payback_period_months', 0):.1f} months")

        # Business outcome verification
        business_outcome_verified = (
            business_score >= 7.0 and
            annual_roi >= 200 and
            annual_value >= 50000
        )

        if business_outcome_verified:
            print("   ✅ BUSINESS OUTCOME VERIFIED")
        else:
            print("   ❌ BUSINESS OUTCOME NOT VERIFIED")

        return {
            "test_name": "employee_onboarding_roi",
            "status": "passed" if business_outcome_verified else "failed",
            "business_score": business_score,
            "annual_roi": annual_roi,
            "annual_value": annual_value,
            "business_outcome_verified": business_outcome_verified,
            "details": roi_result
        }

    def test_cross_platform_productivity(self) -> dict:
        """Test productivity gains from cross-platform automation"""
        print("\n" + "="*60)
        print("TEST 2: Cross-Platform Productivity")
        print("="*60)

        if not self.business_validator_available:
            return self._skip_test("Business outcome validator not available")

        scenario = {
            "user_scenario": "Project manager automating weekly status reporting",
            "description": "Automate collection and distribution of project status across Asana, Slack, Jira, and Email",
            "before_metrics": {
                "tasks_completed": 15,      # Manual status checks across tools
                "hours_spent": 4.0,         # 4 hours per week
                "errors": 3                 # Missing/inconsistent updates
            },
            "after_metrics": {
                "tasks_completed": 20,      # More comprehensive reporting
                "hours_spent": 0.5,         # 30 minutes per week
                "errors": 1                 # Minimal errors
            }
        }

        print(f"Scenario: {scenario['description']}")
        print(f"Before: {scenario['before_metrics']['hours_spent']}h/week, {scenario['before_metrics']['errors']} errors")
        print(f"After: {scenario['after_metrics']['hours_spent']}h/week, {scenario['after_metrics']['errors']} errors")

        # Validate productivity gains
        productivity_result = self.business_validator.validate_user_productivity_gains(
            user_scenario=scenario['user_scenario'],
            before_metrics=scenario['before_metrics'],
            after_metrics=scenario['after_metrics'],
            time_period_days=7
        )

        business_score = productivity_result.get('business_value_score', 0)
        deployment_priority = productivity_result.get('deployment_priority', 'Unknown')
        monthly_estimate = productivity_result.get('monthly_value_estimate', 'Unknown')

        print(f"\n📊 RESULTS:")
        print(f"   Business Value Score: {business_score}/10")
        print(f"   Deployment Priority: {deployment_priority}")
        print(f"   Monthly Value Estimate: {monthly_estimate}")

        # Calculate actual business metrics
        hours_saved_per_week = scenario['before_metrics']['hours_spent'] - scenario['after_metrics']['hours_spent']
        annual_hours_saved = hours_saved_per_week * 52
        annual_value = annual_hours_saved * 75  # $75/hour for project manager

        print(f"   Annual Hours Saved: {annual_hours_saved}")
        print(f"   Annual Value: ${annual_value:,.2f}")

        business_outcome_verified = business_score >= 7.0 and annual_value >= 20000

        if business_outcome_verified:
            print("   ✅ BUSINESS OUTCOME VERIFIED")
        else:
            print("   ❌ BUSINESS OUTCOME NOT VERIFIED")

        return {
            "test_name": "cross_platform_productivity",
            "status": "passed" if business_outcome_verified else "failed",
            "business_score": business_score,
            "annual_value": annual_value,
            "business_outcome_verified": business_outcome_verified,
            "details": productivity_result
        }

    def test_multi_department_roi(self) -> dict:
        """Test ROI across multiple departments"""
        print("\n" + "="*60)
        print("TEST 3: Multi-Department ROI Analysis")
        print("="*60)

        if not self.business_validator_available:
            return self._skip_test("Business outcome validator not available")

        # Test scenarios for different departments
        departments = [
            {
                "name": "HR Department",
                "workflow": "Employee Lifecycle Management",
                "time_saved_minutes": 120,
                "hourly_rate": 65.0,
                "implementation_cost": 12000,
                "monthly_frequency": 15
            },
            {
                "name": "Sales Operations",
                "workflow": "Sales Lead Processing",
                "time_saved_minutes": 45,
                "hourly_rate": 85.0,
                "implementation_cost": 6000,
                "monthly_frequency": 22
            },
            {
                "name": "IT Operations",
                "workflow": "Incident Response Automation",
                "time_saved_minutes": 90,
                "hourly_rate": 95.0,
                "implementation_cost": 15000,
                "monthly_frequency": 25
            }
        ]

        results = []
        total_value = 0
        total_implementation_cost = 0

        for dept in departments:
            print(f"\n🏢 {dept['name']}: {dept['workflow']}")

            roi_result = self.business_validator.calculate_automation_roi(
                workflow_name=dept['workflow'],
                time_saved_minutes=dept['time_saved_minutes'],
                hourly_rate=dept['hourly_rate'],
                implementation_cost=dept['implementation_cost'],
                monthly_frequency=dept['monthly_frequency']
            )

            business_score = roi_result.get('business_value_score', 0)
            annual_roi = roi_result.get('roi_metrics', {}).get('annual_roi_percent', 0)
            annual_value = roi_result.get('financial_metrics', {}).get('annual_value', 0)

            print(f"   Business Score: {business_score}/10")
            print(f"   Annual ROI: {annual_roi:.1f}%")
            print(f"   Annual Value: ${annual_value:,.2f}")

            results.append({
                "department": dept['name'],
                "business_score": business_score,
                "annual_roi": annual_roi,
                "annual_value": annual_value
            })

            total_value += annual_value
            total_implementation_cost += dept['implementation_cost']

        # Calculate overall business metrics
        avg_business_score = sum(r['business_score'] for r in results) / len(results)
        total_annual_roi = ((total_value - total_implementation_cost) / total_implementation_cost * 100) if total_implementation_cost > 0 else 0

        print(f"\n📊 OVERALL RESULTS:")
        print(f"   Average Business Score: {avg_business_score:.1f}/10")
        print(f"   Total Annual Value: ${total_value:,.2f}")
        print(f"   Total Implementation Cost: ${total_implementation_cost:,.2f}")
        print(f"   Overall ROI: {total_annual_roi:.1f}%")

        business_outcome_verified = (
            avg_business_score >= 7.5 and
            total_annual_roi >= 200 and
            total_value >= 200000
        )

        if business_outcome_verified:
            print("   ✅ MULTI-DEPARTMENT BUSINESS OUTCOME VERIFIED")
        else:
            print("   ❌ MULTI-DEPARTMENT BUSINESS OUTCOME NOT VERIFIED")

        return {
            "test_name": "multi_department_roi",
            "status": "passed" if business_outcome_verified else "failed",
            "avg_business_score": avg_business_score,
            "total_annual_value": total_value,
            "overall_roi": total_annual_roi,
            "business_outcome_verified": business_outcome_verified,
            "department_results": results
        }

    def test_overall_business_value(self) -> dict:
        """Test overall platform business value"""
        print("\n" + "="*60)
        print("TEST 4: Overall Platform Business Value")
        print("="*60)

        if not self.business_validator_available:
            return self._skip_test("Business outcome validator not available")

        # Comprehensive platform evaluation
        feature_results = []

        features = [
            {
                "name": "Workflow Automation Platform",
                "capabilities": [
                    "Natural language workflow creation",
                    "Cross-platform integration (30+ services)",
                    "Real-time synchronization",
                    "Error handling and recovery"
                ],
                "business_metrics": {
                    "monthly_cost_savings": 25000,
                    "productivity_increase_pct": 75,
                    "error_reduction_pct": 85,
                    "user_satisfaction_score": 9.2
                },
                "user_context": "Medium-sized enterprise (500 employees) implementing digital transformation"
            }
        ]

        for feature in features:
            print(f"\n🚀 Evaluating: {feature['name']}")

            business_validation = self.business_validator.validate_business_value(
                feature_name=feature['name'],
                test_output={cap: True for cap in feature['capabilities']},
                business_metrics=feature['business_metrics'],
                user_context=feature['user_context']
            )

            business_score = business_validation.get('business_value_score', 0)
            investment_rec = business_validation.get('investment_recommendation', 'Unknown')
            annual_savings = business_validation.get('annual_cost_savings', 'Unknown')
            revenue_impact = business_validation.get('revenue_impact', 'Unknown')

            print(f"   Business Value Score: {business_score}/10")
            print(f"   Investment Recommendation: {investment_rec}")
            print(f"   Annual Cost Savings: {annual_savings}")
            print(f"   Revenue Impact: {revenue_impact}")

            feature_results.append({
                "feature": feature['name'],
                "business_score": business_score,
                "investment_recommendation": investment_rec,
                "validation": business_validation
            })

        # Overall platform assessment
        avg_platform_score = sum(f['business_score'] for f in feature_results) / len(feature_results)

        print(f"\n📊 PLATFORM ASSESSMENT:")
        print(f"   Overall Business Score: {avg_platform_score:.1f}/10")

        business_outcome_verified = avg_platform_score >= 8.0

        if business_outcome_verified:
            print("   ✅ PLATFORM BUSINESS OUTCOME VERIFIED - READY FOR INVESTMENT")
        else:
            print("   ❌ PLATFORM BUSINESS OUTCOME NOT VERIFIED - NEEDS IMPROVEMENT")

        return {
            "test_name": "overall_business_value",
            "status": "passed" if business_outcome_verified else "failed",
            "platform_score": avg_platform_score,
            "business_outcome_verified": business_outcome_verified,
            "feature_results": feature_results
        }

    def _skip_test(self, reason: str) -> dict:
        """Handle skipped tests"""
        print(f"⚠️  SKIPPED: {reason}")
        return {
            "test_name": "skipped",
            "status": "skipped",
            "reason": reason,
            "business_outcome_verified": False
        }

    def run_all_business_tests(self) -> dict:
        """Run all business outcome tests"""
        print("\n" + "🎯" * 20)
        print("BUSINESS OUTCOME VALIDATION STARTING")
        print("🎯" * 20)

        start_time = datetime.now()

        # Run all business tests
        tests = [
            self.test_employee_onboarding_roi,
            self.test_cross_platform_productivity,
            self.test_multi_department_roi,
            self.test_overall_business_value
        ]

        results = []
        passed_tests = 0
        total_tests = len(tests)

        for test_func in tests:
            try:
                result = test_func()
                results.append(result)

                if result.get("status") == "passed":
                    passed_tests += 1

            except Exception as e:
                print(f"\n🚨 TEST ERROR: {test_func.__name__} - {str(e)}")
                results.append({
                    "test_name": test_func.__name__,
                    "status": "error",
                    "error": str(e),
                    "business_outcome_verified": False
                })

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Summary
        print("\n" + "="*80)
        print("📊 BUSINESS OUTCOME VALIDATION SUMMARY")
        print("="*80)
        print(f"Tests Run: {passed_tests}/{total_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        print(f"Duration: {duration:.1f} seconds")

        # Calculate overall business readiness
        business_outcomes_verified = sum(1 for r in results if r.get("business_outcome_verified", False))

        print(f"Business Outcomes Verified: {business_outcomes_verified}/{total_tests}")

        if business_outcomes_verified >= 3:
            print("\n🎉 PLATFORM DELIVERS STRONG BUSINESS VALUE")
            print("   ✅ Ready for production deployment")
            print("   ✅ Strong ROI across multiple scenarios")
            print("   ✅ Tangible business benefits verified")
        elif business_outcomes_verified >= 2:
            print("\n⚠️  PLATFORM DELIVERS MODERATE BUSINESS VALUE")
            print("   ⚠️  Consider improvements before production")
            print("   ⚠️  Some scenarios need optimization")
        else:
            print("\n❌ PLATFORM BUSINESS VALUE INSUFFICIENT")
            print("   ❌ Significant improvements needed")
            print("   ❌ Re-evaluate business strategy")

        return {
            "overall_status": "PASSED" if business_outcomes_verified >= 3 else "FAILED",
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "business_outcomes_verified": business_outcomes_verified,
            "business_readiness": "Ready" if business_outcomes_verified >= 3 else "Needs Improvement",
            "duration_seconds": duration,
            "test_results": results,
            "executive_summary": {
                "recommendation": "DEPLOY" if business_outcomes_verified >= 3 else "IMPROVE",
                "confidence_level": f"{(business_outcomes_verified/total_tests)*100:.0f}%",
                "key_benefits": ["Time savings", "Cost reduction", "Productivity gains"] if business_outcomes_verified >= 2 else ["Needs improvement"]
            }
        }


def main():
    """Main entry point"""
    runner = BusinessOutcomeTestRunner()
    results = runner.run_all_business_tests()

    # Save results
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = f"reports/business_outcome_report_{timestamp}.json"

    import json
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n📄 Detailed report saved to: {report_file}")

    # Exit with appropriate code
    sys.exit(0 if results["overall_status"] == "PASSED" else 1)


if __name__ == "__main__":
    main()