#!/usr/bin/env node
/**
 * Coverage Audit Script - Phase 130-01
 * Generates per-module coverage report from coverage-summary.json
 * Usage: node scripts/coverage-audit.js [--format json|markdown|console]
 */

const fs = require('fs');
const path = require('path');

const COVERAGE_FILE = path.join(__dirname, '../coverage/coverage-summary.json');
const MODULE_CATEGORIES = {
  'components/canvas': { name: 'Canvas Components', threshold: 85 },
  'components/integrations': { name: 'Integration Components', threshold: 70 },
  'components/ui': { name: 'UI Components', threshold: 80 },
  'lib': { name: 'Utility Libraries', threshold: 90 },
  'hooks': { name: 'React Hooks', threshold: 85 },
  'pages': { name: 'Next.js Pages', threshold: 80 },
};

function loadCoverage() {
  if (!fs.existsSync(COVERAGE_FILE)) {
    console.error(`Coverage file not found: ${COVERAGE_FILE}`);
    console.error('Run: npm run test:coverage');
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(COVERAGE_FILE, 'utf8'));
}

function categorizeFile(filepath) {
  for (const [pattern, category] of Object.entries(MODULE_CATEGORIES)) {
    if (filepath.includes(pattern)) {
      return { pattern, ...category };
    }
  }
  return { pattern: 'other', name: 'Other', threshold: 80 };
}

function aggregateModuleCoverage(coverage) {
  const modules = {};
  let total = { lines: { covered: 0, total: 0 }, files: 0 };

  for (const [filepath, metrics] of Object.entries(coverage)) {
    if (filepath === 'total') continue;

    const category = categorizeFile(filepath);

    if (!modules[category.pattern]) {
      modules[category.pattern] = {
        name: category.name,
        threshold: category.threshold,
        files: [],
        lines: { covered: 0, total: 0 },
        branches: { covered: 0, total: 0 },
        functions: { covered: 0, total: 0 },
      };
    }

    modules[category.pattern].files.push({
      path: filepath,
      lines: metrics.lines.pct,
      branches: metrics.branches.pct,
      functions: metrics.functions.pct,
    });

    modules[category.pattern].lines.covered += metrics.lines.covered;
    modules[category.pattern].lines.total += metrics.lines.total;
    modules[category.pattern].branches.covered += metrics.branches.covered;
    modules[category.pattern].branches.total += metrics.branches.total;
    modules[category.pattern].functions.covered += metrics.functions.covered;
    modules[category.pattern].functions.total += metrics.functions.total;

    total.lines.covered += metrics.lines.covered;
    total.lines.total += metrics.lines.total;
    total.files++;
  }

  // Calculate percentages
  for (const module of Object.values(modules)) {
    module.lines.pct = module.lines.total > 0
      ? Math.round((module.lines.covered / module.lines.total) * 100)
      : 0;
    module.branches.pct = module.branches.total > 0
      ? Math.round((module.branches.covered / module.branches.total) * 100)
      : 0;
    module.functions.pct = module.functions.total > 0
      ? Math.round((module.functions.covered / module.functions.total) * 100)
      : 0;
    module.gap = Math.max(0, module.threshold - module.lines.pct);
    module.status = module.lines.pct >= module.threshold ? 'PASS' : 'GAP';
  }

  total.pct = total.lines.total > 0
    ? Math.round((total.lines.covered / total.lines.total) * 100)
    : 0;

  return { modules, total };
}

function generateReport(coverage, format = 'console') {
  const { modules, total } = aggregateModuleCoverage(coverage);

  if (format === 'json') {
    return JSON.stringify({ modules, total, timestamp: new Date().toISOString() }, null, 2);
  }

  if (format === 'markdown') {
    let md = `# Frontend Coverage Audit Report\n\n`;
    md += `**Generated:** ${new Date().toISOString()}\n`;
    md += `**Overall Coverage:** ${total.pct}% (${total.lines.covered}/${total.lines.total} lines)\n\n`;
    md += `## Module Breakdown\n\n`;
    md += `| Module | Files | Lines | Branches | Functions | Threshold | Status | Gap |\n`;
    md += `|--------|-------|-------|----------|-----------|-----------|--------|-----|\n`;

    for (const [key, module] of Object.entries(modules)) {
      const status = module.status === 'PASS' ? 'PASS' : 'FAIL';
      md += `| ${module.name} | ${module.files.length} | ${module.lines.pct}% | ${module.branches.pct}% | ${module.functions.pct}% | ${module.threshold}% | ${status} | ${module.gap}% |\n`;
    }

    md += `\n## Coverage Gaps\n\n`;
    const gaps = Object.values(modules).filter(m => m.status === 'GAP').sort((a, b) => b.gap - a.gap);
    for (const gap of gaps) {
      md += `### ${gap.name} (${gap.lines.pct}% - ${gap.gap}% below threshold)\n`;
      const worstFiles = gap.files.filter(f => f.lines < gap.threshold).sort((a, b) => a.lines - b.lines);
      for (const file of worstFiles.slice(0, 10)) {
        md += `- ${file.path}: ${file.lines}%\n`;
      }
      md += `\n`;
    }

    return md;
  }

  // Console format
  console.log(`\n=== FRONTEND COVERAGE AUDIT ===\n`);
  console.log(`Overall: ${total.pct}% (${total.lines.covered}/${total.lines.total} lines)\n`);
  console.log(`Module Breakdown:\n`);

  for (const [key, module] of Object.values(modules)) {
    const status = module.lines.pct >= module.threshold ? '✓' : '✗';
    console.log(`${status} ${module.name.padEnd(25)} ${module.lines.pct.toString().padStart(3)}% (threshold: ${module.threshold}%, gap: ${module.gap}%)`);
  }

  console.log(`\nGaps (${Object.values(modules).filter(m => m.status === 'GAP').length} modules below threshold):\n`);
  for (const gap of Object.values(modules).filter(m => m.status === 'GAP').sort((a, b) => a.lines.pct - b.lines.pct)) {
    console.log(`  ${gap.name}: ${gap.lines.pct}% (${gap.gap}% below threshold)`);
  }

  return { modules, total };
}

// CLI
const args = process.argv.slice(2);
const format = args.find(a => a.startsWith('--format='))?.split('=')[1] || 'console';
const coverage = loadCoverage();
const report = generateReport(coverage, format);

if (format === 'json' || format === 'markdown') {
  console.log(report);
}
