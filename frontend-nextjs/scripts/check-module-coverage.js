#!/usr/bin/env node
/**
 * Module Coverage Check Script - Phase 130-05
 * Enforces per-module coverage thresholds
 * Usage: node scripts/check-module-coverage.js [--threshold 80] [--reporter github-actions|console|json]
 */

const fs = require('fs');
const path = require('path');

const COVERAGE_FILE = path.join(__dirname, '../coverage/coverage-summary.json');

// Module thresholds (must match jest.config.js)
const THRESHOLDS = {
  './lib/**/*.{ts,tsx}': { lines: 90, name: 'Utility Libraries' },
  './hooks/**/*.{ts,tsx}': { lines: 85, name: 'React Hooks' },
  './components/canvas/**/*.{ts,tsx}': { lines: 85, name: 'Canvas Components' },
  './components/ui/**/*.{ts,tsx}': { lines: 75, name: 'UI Components' },
  './components/integrations/**/*.{ts,tsx}': { lines: 75, name: 'Integration Components' },
  './pages/**/*.{ts,tsx}': { lines: 75, name: 'Next.js Pages' },
};

function getThresholdForFile(filepath) {
  for (const [pattern, config] of Object.entries(THRESHOLDS)) {
    const regexPattern = pattern
      .replace('./', '')
      .replace('/**/*.{ts,tsx}', '')
      .replace('*', '.*');
    if (filepath.match(regexPattern)) {
      return config;
    }
  }
  return { lines: 80, name: 'Other' };
}

function loadCoverage() {
  if (!fs.existsSync(COVERAGE_FILE)) {
    console.error(`::error::Coverage file not found: ${COVERAGE_FILE}`);
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(COVERAGE_FILE, 'utf8'));
}

function checkModuleCoverage(coverage) {
  const results = {
    passed: [],
    failed: [],
    summary: {},
  };

  const moduleAggregates = {};

  for (const [filepath, metrics] of Object.entries(coverage)) {
    if (filepath === 'total') {
      results.summary = {
        lines: metrics.lines.pct,
        branches: metrics.branches.pct,
        functions: metrics.functions.pct,
        statements: metrics.statements.pct,
      };
      continue;
    }

    const threshold = getThresholdForFile(filepath);
    const moduleKey = threshold.name;

    if (!moduleAggregates[moduleKey]) {
      moduleAggregates[moduleKey] = {
        name: threshold.name,
        threshold: threshold.lines,
        files: [],
        lines: { covered: 0, total: 0 },
      };
    }

    moduleAggregates[moduleKey].files.push({
      path: filepath,
      coverage: metrics.lines.pct,
    });
    moduleAggregates[moduleKey].lines.covered += metrics.lines.covered;
    moduleAggregates[moduleKey].lines.total += metrics.lines.total;
  }

  // Calculate module-level coverage and check thresholds
  for (const module of Object.values(moduleAggregates)) {
    module.lines.pct = module.lines.total > 0
      ? Math.round((module.lines.covered / module.lines.total) * 100)
      : 0;
    module.gap = module.threshold - module.lines.pct;
    module.passed = module.lines.pct >= module.threshold;

    if (module.passed) {
      results.passed.push(module);
    } else {
      results.failed.push(module);
    }
  }

  results.modules = moduleAggregates;
  return results;
}

function generateGitHubActionsReport(results) {
  let output = '\n## Frontend Module Coverage Report\n\n';

  // Summary
  output += `**Overall Coverage:** ${results.summary.lines}% (lines)\n\n`;

  // Passed modules
  if (results.passed.length > 0) {
    output += '### ✅ Passed Modules\n\n';
    output += '| Module | Coverage | Threshold |\n';
    output += '|--------|----------|-----------|\n';
    for (const mod of results.passed) {
      output += `| ${mod.name} | ${mod.lines.pct}% | ${mod.threshold}% |\n`;
    }
    output += '\n';
  }

  // Failed modules
  if (results.failed.length > 0) {
    output += '### ❌ Failed Modules\n\n';
    output += '| Module | Coverage | Threshold | Gap |\n';
    output += '|--------|----------|-----------|-----|\n';
    for (const mod of results.failed) {
      output += `| ${mod.name} | ${mod.lines.pct}% | ${mod.threshold}% | ${mod.gap}% |\n`;
    }
    output += '\n';

    // Worst files for each failed module
    output += '#### Files Below Threshold\n\n';
    for (const mod of results.failed) {
      output += `**${mod.name}:**\n`;
      const worstFiles = mod.files
        .filter(f => f.coverage < mod.threshold)
        .sort((a, b) => a.coverage - b.coverage)
        .slice(0, 5);
      for (const file of worstFiles) {
        output += `- ${file.path}: ${file.coverage}%\n`;
      }
      output += '\n';
    }
  }

  // GitHub Actions annotations for failures
  for (const mod of results.failed) {
    console.log(`::error::Module "${mod.name}" below threshold: ${mod.lines.pct}% < ${mod.threshold}%`);
    for (const file of mod.files.filter(f => f.coverage < mod.threshold).slice(0, 3)) {
      console.log(`::warning file=${file.path}::Coverage: ${file.coverage}% (threshold: ${mod.threshold}%)`);
    }
  }

  return output;
}

function generateConsoleReport(results) {
  console.log(`\n=== MODULE COVERAGE CHECK ===\n`);
  console.log(`Overall: ${results.summary.lines}% lines\n`);

  console.log(`Passed (${results.passed.length}):`);
  for (const mod of results.passed) {
    console.log(`  ✓ ${mod.name.padEnd(25)} ${mod.lines.pct}% >= ${mod.threshold}%`);
  }

  if (results.failed.length > 0) {
    console.log(`\nFailed (${results.failed.length}):`);
    for (const mod of results.failed) {
      console.log(`  ✗ ${mod.name.padEnd(25)} ${mod.lines.pct}% < ${mod.threshold}% (${mod.gap}% gap)`);
    }
  }

  console.log('');
  return results.failed.length === 0;
}

function generateJsonReport(results) {
  return JSON.stringify({
    passed: results.failed.length === 0,
    summary: results.summary,
    modules: results.modules,
    failed: results.failed,
    timestamp: new Date().toISOString(),
  }, null, 2);
}

// CLI
const args = process.argv.slice(2);
const reporter = args.find(a => a.startsWith('--reporter='))?.split('=')[1] || 'console';

const coverage = loadCoverage();
const results = checkModuleCoverage(coverage);

if (reporter === 'github-actions') {
  console.log(generateGitHubActionsReport(results));
  process.exit(results.failed.length > 0 ? 1 : 0);
} else if (reporter === 'json') {
  console.log(generateJsonReport(results));
  process.exit(results.failed.length > 0 ? 1 : 0);
} else {
  const passed = generateConsoleReport(results);
  process.exit(passed ? 0 : 1);
}
