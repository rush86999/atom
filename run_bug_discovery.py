#!/usr/bin/env python3
import sys
sys.path.insert(0, 'backend')

from tests.bug_discovery.feedback_loops.bug_execution_orchestrator import BugExecutionOrchestrator
from tests.bug_discovery.feedback_loops.bug_remediation_service import BugRemediationService
import json
from datetime import datetime

def main():
    print("=" * 60)
    print("STARTING BUG DISCOVERY CYCLE")
    print("=" * 60)
    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("Time: " + str(time_str))
    print()

    orchestrator = BugExecutionOrchestrator()

    # Run discovery - skip chaos (requires isolation) and AI (for speed)
    print("Running bug discovery methods...")
    print("  Fuzzing: enabled")
    print("  Chaos: disabled (requires isolation)")
    print("  Property: enabled")
    print("  Browser: enabled")
    print("  Memory: enabled")
    print("  Performance: enabled")
    print("  AI-Enhanced: disabled (for speed)")
    print()

    results = orchestrator.run_full_discovery_cycle(
        run_fuzzing=True,
        run_chaos=False,  # Skip chaos (requires Toxiproxy isolation)
        run_property=True,
        run_browser=True,
        run_memory=True,
        run_performance=True,
        run_ai_enhanced=False  # Skip AI for faster execution
    )

    print()
    print("=" * 60)
    print("DISCOVERY RESULTS")
    print("=" * 60)
    print(f"Bugs found: {results['bugs_found']}")
    print(f"Unique bugs: {results['unique_bugs']}")
    print(f"Duration: {results['duration_seconds']:.1f} seconds")
    print()
    print("By Severity:")
    for severity, count in results['bugs_by_severity'].items():
        print(f"  {severity}: {count}")
    print()
    print("By Discovery Method:")
    for method, count in results['bugs_by_method'].items():
        print(f"  {method}: {count}")
    print()

    # Save results
    output_file = '.planning/phases/245-feedback-loops-and-roi-tracking/discovery_results.json'
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"Results saved to: {output_file}")
    print()
    print("=" * 60)
    print("DISCOVERY CYCLE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
