#!/usr/bin/env node

/**
 * Jest Retry Wrapper for Flaky Test Detection
 *
 * Run Jest tests multiple times to detect intermittent failures (flaky tests).
 * This implements multi-run flaky detection for frontend tests, matching the
 * Python pytest-rerunfailures pattern used in the backend.
 *
 * Usage:
 *   node scripts/jest-retry-wrapper.js --testPattern="AgentCard" --runs=3
 *   node scripts/jest-retry-wrapper.js --testPattern="Canvas" --runs=10 --output=coverage/test_flaky.json
 *
 * See: .planning/phases/151-quality-infrastructure-reliability/151-RESEARCH.md (Pattern 1)
 */

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Parse CLI arguments using minimist-style parsing
function parseArgs(args) {
  const parsed = {
    testPattern: null,
    runs: 10,
    output: 'coverage/frontend_flaky_tests.json',
    platform: 'frontend',
    verbose: false,
  };

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];
    if (arg.startsWith('--testPattern=')) {
      parsed.testPattern = arg.split('=')[1];
    } else if (arg.startsWith('--runs=')) {
      parsed.runs = parseInt(arg.split('=')[1], 10);
    } else if (arg.startsWith('--output=')) {
      parsed.output = arg.split('=')[1];
    } else if (arg.startsWith('--platform=')) {
      parsed.platform = arg.split('=')[1];
    } else if (arg === '--verbose') {
      parsed.verbose = true;
    }
  }

  return parsed;
}

/**
 * Run a Jest test multiple times to detect flakiness.
 *
 * @param {string} testPattern - Jest test name pattern (e.g., "AgentCard", "Canvas")
 * @param {number} runs - Number of times to run the test
 * @param {boolean} verbose - Enable verbose logging
 * @returns {Object} Test execution results with classification
 */
function runTestMultipleTimes(testPattern, runs, verbose = false) {
  const failures = [];
  const failureDetails = [];

  for (let i = 0; i < runs; i++) {
    const startTime = Date.now();

    try {
      if (verbose) {
        console.log(`[Run ${i + 1}/${runs}] Executing: jest --testNamePattern="${testPattern}"`);
      }

      execSync(
        `jest --testNamePattern="${testPattern}" --passWithNoTests`,
        {
          stdio: verbose ? 'inherit' : 'pipe',
          timeout: 30000, // 30s timeout per run
        }
      );

      const duration = Date.now() - startTime;
      if (verbose) {
        console.log(`[Run ${i + 1}/${runs}] PASSED (${duration}ms)`);
      }

      failures.push(false);
      failureDetails.push({ run: i, failed: false, duration });
    } catch (error) {
      const duration = Date.now() - startTime;

      // Test failure is expected for flaky detection
      if (verbose) {
        console.log(`[Run ${i + 1}/${runs}] FAILED (${duration}ms)`);
      }

      failures.push(true);
      failureDetails.push({
        run: i,
        failed: true,
        duration,
        error: error.message ? error.message.substring(0, 200) : 'Unknown error',
      });
    }
  }

  const failureCount = failures.filter((f) => f).length;
  const flakyRate = failureCount / runs;

  // Classify flakiness
  let classification;
  if (failureCount === 0) {
    classification = 'stable';
  } else if (failureCount === runs) {
    classification = 'broken';
  } else {
    classification = 'flaky';
  }

  return {
    testPattern,
    totalRuns: runs,
    failures: failureCount,
    flakyRate: parseFloat(flakyRate.toFixed(3)),
    classification,
    failureDetails,
  };
}

/**
 * Classify test flakiness based on failure count.
 *
 * @param {number} failureCount - Number of failed test runs
 * @param {number} totalRuns - Total number of test runs
 * @returns {string} Classification: 'stable', 'flaky', or 'broken'
 */
function classifyFlakiness(failureCount, totalRuns) {
  if (failureCount === 0) {
    return 'stable';
  } else if (failureCount === totalRuns) {
    return 'broken';
  } else {
    return 'flaky';
  }
}

/**
 * Export flaky test results to JSON file.
 *
 * @param {Object} results - Test execution results
 * @param {string} outputPath - JSON output file path
 * @param {string} platform - Platform name (e.g., 'frontend', 'mobile')
 */
function exportResults(results, outputPath, platform) {
  const outputDir = path.dirname(outputPath);

  // Create output directory if it doesn't exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  const exportData = {
    scan_date: new Date().toISOString(),
    platform,
    test_pattern: results.testPattern,
    total_runs: results.totalRuns,
    failures: results.failures,
    flaky_rate: results.flakyRate,
    classification: results.classification,
    failure_details: results.failureDetails,
  };

  fs.writeFileSync(outputPath, JSON.stringify(exportData, null, 2));
  console.log(`\nResults exported to: ${outputPath}`);
}

/**
 * Print summary of test execution.
 *
 * @param {Object} results - Test execution results
 */
function printSummary(results) {
  console.log('\n=== Jest Retry Wrapper Summary ===');
  console.log(`Test Pattern: ${results.testPattern}`);
  console.log(`Total Runs: ${results.totalRuns}`);
  console.log(`Failures: ${results.failures}`);
  console.log(`Flaky Rate: ${(results.flakyRate * 100).toFixed(1)}%`);
  console.log(`Classification: ${results.classification.toUpperCase()}`);

  if (results.classification === 'flaky') {
    console.log('\n⚠️  FLAKY TEST DETECTED');
    console.log('   This test intermittently fails and should be investigated.');
    console.log('   Consider adding @pytest.mark.flaky (Python) or jest.retryTimes() (Jest)');
  } else if (results.classification === 'broken') {
    console.log('\n❌ BROKEN TEST DETECTED');
    console.log('   This test consistently fails and needs to be fixed.');
  } else {
    console.log('\n✅ STABLE TEST');
    console.log('   This test passes consistently across all runs.');
  }
}

/**
 * Main execution function.
 */
function main() {
  const args = parseArgs(process.argv.slice(2));

  // Validate required arguments
  if (!args.testPattern) {
    console.error('Error: --testPattern is required');
    console.error('Usage: node jest-retry-wrapper.js --testPattern="AgentCard" --runs=10');
    process.exit(2);
  }

  if (args.runs < 1) {
    console.error('Error: --runs must be at least 1');
    process.exit(2);
  }

  console.log(`=== Jest Retry Wrapper (${args.platform}) ===`);
  console.log(`Test Pattern: ${args.testPattern}`);
  console.log(`Runs: ${args.runs}`);
  console.log(`Output: ${args.output}`);
  console.log('');

  try {
    // Run test multiple times
    const results = runTestMultipleTimes(args.testPattern, args.runs, args.verbose);

    // Print summary
    printSummary(results);

    // Export to JSON
    exportResults(results, args.output, args.platform);

    // Exit codes: 0 (stable), 1 (flaky found), 2 (execution error)
    if (results.classification === 'flaky') {
      process.exit(1);
    } else if (results.classification === 'broken') {
      process.exit(1);
    } else {
      process.exit(0);
    }
  } catch (error) {
    console.error(`\nExecution error: ${error.message}`);
    process.exit(2);
  }
}

// Execute main function
if (require.main === module) {
  main();
}

module.exports = {
  runTestMultipleTimes,
  classifyFlakiness,
  exportResults,
};
