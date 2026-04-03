#!/usr/bin/env python3
"""
Non-interactive E2E test runner with auto-loaded credentials
Loads credentials from environment and runs comprehensive tests
"""
import asyncio
import os
import sys

# Pre-set credentials in environment (these will be loaded if available)
# The E2E tester will pick them up automatically
ENV_VARS = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY', ''),
    'ANTHROPIC_API_KEY': os.getenv('ANTHROPIC_API_KEY', ''),
    'DEEPSEEK_API_KEY': os.getenv('DEEPSEEK_API_KEY', ''),
    'GLM_API_KEY': os.getenv('GLM_API_KEY', ''),
    'SLACK_BOT_TOKEN': os.getenv('SLACK_BOT_TOKEN', ''),
    'GITHUB_ACCESS_TOKEN': os.getenv('GITHUB_ACCESS_TOKEN', ''),
    'ASANA_TOKEN': os.getenv('ASANA_TOKEN', ''),
    'NOTION_TOKEN': os.getenv('NOTION_TOKEN', ''),
}

for key, val in ENV_VARS.items():
    if val:
        os.environ[key] = val

# Import after setting env vars
from comprehensive_e2e_integration_tester import ComprehensiveE2ETester


async def main():
    print('🚀 Running Non-Interactive E2E Tests with Backend Active')
    print('='*80)
    
    tester = ComprehensiveE2ETester()
    
    # Run tests
    try:
        results = await tester.run_comprehensive_tests()
        
        # Display results
        print('\n' + '='*80)
        print('📊 TEST RESULTS')
        print('='*80)
        
        if 'overall_success_rate' in results:
            print(f'Success Rate: {results["overall_success_rate"]*100:.1f}%')
            print(f'Passed: {results["passed_tests"]}/{results["total_tests"]}')
            print(f'Failed: {results["failed_tests"]}')
            print(f'Skipped: {results["skipped_tests"]}')
            print(f'Gap to 98% Target: {98 - results["overall_success_rate"]*100:.1f}%')
            
            # Category breakdown
            print('\n📋 CATEGORY BREAKDOWN:')
            for cat, stats in results.get('category_breakdown', {}).items():
                print(f'  {cat}: {stats.get("passed", 0)}/{stats.get("total", 0)} passed')
            
            # Gap analysis
            gap = results.get('gap_analysis', {})
            print(f'\n🔍 Issues Found: {gap.get("bug_count", 0)} bugs, {gap.get("gap_count", 0)} gaps')
            
            # Return exit code based on success
            if results["overall_success_rate"] >= 0.9:
                print('\n✅ Launch Ready (>90% pass rate)!')
                sys.exit(0)
            else:
                print(f'\n⚠️ Not launch ready. Need {90 - results["overall_success_rate"]*100:.1f}% improvement')
                sys.exit(1)
        else:
            print('❌ Test results incomplete')
            sys.exit(1)
            
    except Exception as e:
        print(f'❌ Test execution failed: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
