#!/usr/bin/env python3
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from independent_ai_validator.core.business_outcome_validator import BusinessOutcomeValidator

async def run_validation():
    print("=" * 80)
    print("ATOM BUSINESS OUTCOME VALIDATION")
    print("=" * 80)
    print("Focus: Verifying Value Delivery (Time Savings, Efficiency, Automation)")
    print("-" * 80)
    
    validator = BusinessOutcomeValidator("http://localhost:8000")
    results = await validator.validate_business_outcomes()
    
    print(f"\nValidation Complete at {results['timestamp']}")
    print(f"Total Value Score: {results['total_value_score']:.2f}/1.0\n")
    
    print("SCENARIO RESULTS:")
    print("-" * 40)
    
    for scenario in results["scenarios"]:
        status = "[PASS]" if scenario["success"] else "[FAIL]"
        print(f"{status} | {scenario['scenario']}")
        print(f"   Metric: {scenario['metric']}")
        print(f"   Benchmark (Manual): {scenario['benchmark_manual']}")
        print(f"   Actual (ATOM):      {scenario['actual_system']}")
        print(f"   Value Generated:    {scenario['value_generated']}")
        print("-" * 40)
        
    # Save report
    report_path = Path("backend/business_outcome_report.json")
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed report saved to {report_path}")

if __name__ == "__main__":
    asyncio.run(run_validation())
