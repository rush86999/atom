#!/usr/bin/env node
/**
 * Coverage Gap Analysis Script - Phase 130-02
 * Identifies modules below threshold and prioritizes testing efforts
 * Usage: node scripts/coverage-gaps.js [--threshold 80] [--format json|markdown|console]
 */

const fs = require('fs');
const path = require('path');

const COVERAGE_FILE = path.join(__dirname, '../coverage/coverage-summary.json');
const DEFAULT_THRESHOLD = 80;

// Module thresholds (graduated rollout)
const THRESHOLDS = {
  './lib/**/*.{ts,tsx}': { lines: 90, name: 'Utility Libraries' },
  './hooks/**/*.{ts,tsx}': { lines: 85, name: 'React Hooks' },
  './components/canvas/**/*.{ts,tsx}': { lines: 85, name: 'Canvas Components' },
  './components/ui/**/*.{ts,tsx}': { lines: 80, name: 'UI Components' },
  './components/integrations/**/*.{ts,tsx}': { lines: 70, name: 'Integration Components' },
  './pages/**/*.{ts,tsx}': { lines: 80, name: 'Next.js Pages' },
};

function getThresholdForFile(filepath) {
  // Normalize filepath to relative path for matching
  const relativePath = filepath.replace(/.*\/frontend-nextjs\//, '');

  for (const [pattern, config] of Object.entries(THRESHOLDS)) {
    // Convert glob pattern to regex
    // e.g., './lib/**/*.{ts,tsx}' -> '^lib/'
    const regexPattern = pattern
      .replace('./', '^')
      .replace('/\*\*/\*\.{ts,tsx}', '/')
      .replace('{ts,tsx}', '(ts|tsx)');
    if (relativePath.match(regexPattern)) {
      return config;
    }
  }
  return { lines: DEFAULT_THRESHOLD, name: 'Other' };
}

function loadCoverage() {
  if (!fs.existsSync(COVERAGE_FILE)) {
    console.error(`Coverage file not found: ${COVERAGE_FILE}`);
    console.error('Run: npm run test:coverage');
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(COVERAGE_FILE, 'utf8'));
}

function analyzeGaps(coverage) {
  const gaps = [];
  const moduleSummary = {};

  for (const [filepath, metrics] of Object.entries(coverage)) {
    if (filepath === 'total') continue;

    const threshold = getThresholdForFile(filepath);
    const linePct = metrics.lines.pct;
    const uncovered = metrics.lines.total - metrics.lines.covered;

    // Track module-level summary
    const relativePath = filepath.replace(/.*\/frontend-nextjs\//, '');
    // Use the threshold name as the module key for proper aggregation
    const moduleKey = threshold.name;
    if (!moduleSummary[moduleKey]) {
      moduleSummary[moduleKey] = {
        name: threshold.name,
        threshold: threshold.lines,
        files: [],
        totalLines: 0,
        coveredLines: 0,
      };
    }
    moduleSummary[moduleKey].files.push(relativePath);
    moduleSummary[moduleKey].totalLines += metrics.lines.total;
    moduleSummary[moduleKey].coveredLines += metrics.lines.covered;

    // Identify gaps
    if (linePct < threshold.lines) {
      gaps.push({
        file: relativePath,
        coverage: linePct,
        threshold: threshold.lines,
        uncovered: uncovered,
        gap: threshold.lines - linePct,
        module: threshold.name,
        priority: linePct < 50 ? 'CRITICAL' : linePct < 70 ? 'HIGH' : 'MEDIUM',
      });
    }
  }

  // Calculate module-level coverage
  const modules = Object.entries(moduleSummary).map(([key, data]) => ({
    key,
    ...data,
    coverage: data.totalLines > 0
      ? Math.round((data.coveredLines / data.totalLines) * 100)
      : 0,
    gap: Math.max(0, data.threshold - (data.totalLines > 0
      ? Math.round((data.coveredLines / data.totalLines) * 100)
      : 0)),
  }));

  // Sort gaps by priority and coverage
  gaps.sort((a, b) => {
    const priorityOrder = { CRITICAL: 0, HIGH: 1, MEDIUM: 2 };
    if (priorityOrder[a.priority] !== priorityOrder[b.priority]) {
      return priorityOrder[a.priority] - priorityOrder[b.priority];
    }
    return a.coverage - b.coverage;
  });

  return { gaps, modules };
}

function generateReport(gaps, modules, format = 'console') {
  if (format === 'json') {
    return JSON.stringify({
      gaps,
      modules,
      summary: {
        totalGaps: gaps.length,
        critical: gaps.filter(g => g.priority === 'CRITICAL').length,
        high: gaps.filter(g => g.priority === 'HIGH').length,
        medium: gaps.filter(g => g.priority === 'MEDIUM').length,
      },
      timestamp: new Date().toISOString(),
    }, null, 2);
  }

  if (format === 'markdown') {
    let md = `# Coverage Gap Analysis Report\n\n`;
    md += `**Generated:** ${new Date().toISOString()}\n\n`;
    md += `## Summary\n\n`;
    md += `- **Total Gaps:** ${gaps.length} files below threshold\n`;
    md += `- **CRITICAL:** ${gaps.filter(g => g.priority === 'CRITICAL').length} files (< 50% coverage)\n`;
    md += `- **HIGH:** ${gaps.filter(g => g.priority === 'HIGH').length} files (50-70% coverage)\n`;
    md += `- **MEDIUM:** ${gaps.filter(g => g.priority === 'MEDIUM').length} files (70-80% coverage)\n\n`;

    md += `## Module-Level Coverage\n\n`;
    md += `| Module | Files | Coverage | Threshold | Gap |\n`;
    md += `|--------|-------|----------|-----------|-----|\n`;
    for (const mod of modules.sort((a, b) => a.coverage - b.coverage)) {
      const status = mod.coverage >= mod.threshold ? 'PASS' : 'FAIL';
      md += `| ${mod.name} | ${mod.files.length} | ${mod.coverage}% | ${mod.threshold}% | ${mod.gap}% | ${status} |\n`;
    }

    md += `\n## Critical Gaps (< 50% coverage)\n\n`;
    const critical = gaps.filter(g => g.priority === 'CRITICAL');
    if (critical.length === 0) {
      md += `No critical gaps.\n`;
    } else {
      for (const gap of critical.slice(0, 50)) {
        md += `- **${gap.file}**: ${gap.coverage}% (${gap.uncovered} uncovered lines)\n`;
      }
    }

    md += `\n## High Priority Gaps (50-70% coverage)\n\n`;
    const high = gaps.filter(g => g.priority === 'HIGH');
    if (high.length === 0) {
      md += `No high priority gaps.\n`;
    } else {
      for (const gap of high.slice(0, 50)) {
        md += `- **${gap.file}**: ${gap.coverage}% (${gap.uncovered} uncovered lines)\n`;
      }
    }

    return md;
  }

  // Console format
  console.log(`\n=== COVERAGE GAP ANALYSIS ===\n`);
  console.log(`Total Gaps: ${gaps.length} files below threshold\n`);
  console.log(`Priority Breakdown:`);
  console.log(`  CRITICAL (< 50%): ${gaps.filter(g => g.priority === 'CRITICAL').length} files`);
  console.log(`  HIGH (50-70%): ${gaps.filter(g => g.priority === 'HIGH').length} files`);
  console.log(`  MEDIUM (70-80%): ${gaps.filter(g => g.priority === 'MEDIUM').length} files\n`);

  console.log(`Module-Level Coverage:`);
  for (const mod of modules.sort((a, b) => a.coverage - b.coverage)) {
    const status = mod.coverage >= mod.threshold ? '✓' : '✗';
    console.log(`  ${status} ${mod.name.padEnd(25)} ${mod.coverage.toString().padStart(3)}% (threshold: ${mod.threshold}%, gap: ${mod.gap}%)`);
  }

  console.log(`\nCRITICAL GAPS (top 20):`);
  const critical = gaps.filter(g => g.priority === 'CRITICAL').slice(0, 20);
  critical.forEach(gap => {
    console.log(`  ${gap.coverage.toString().padStart(3)}% | ${gap.uncovered.toString().padStart(4)} uncovered | ${gap.file}`);
  });

  return { gaps, modules };
}

// CLI
const args = process.argv.slice(2);
const thresholdArg = args.find(a => a.startsWith('--threshold='))?.split('=')[1];
const format = args.find(a => a.startsWith('--format='))?.split('=')[1] || 'console';
const coverage = loadCoverage();
const { gaps, modules } = analyzeGaps(coverage);
const report = generateReport(gaps, modules, format);

if (format === 'json' || format === 'markdown') {
  console.log(report);
}
