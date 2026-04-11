const fs = require('fs');

const summary = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));

// Critical component directories
const criticalDirs = {
  agents: /^\/Users\/rushiparikh\/projects\/atom\/frontend-nextjs\/components\/Agents\//,
  automations: /^\/Users\/rushiparikh\/projects\/atom\/frontend-nextjs\/components\/Automations\//,
  canvas: /^\/Users\/rushiparikh\/projects\/atom\/frontend-nextjs\/components\/canvas\//,
  auth: /^\/Users\/rushiparikh\/projects\/atom\/frontend-nextjs\/pages\/auth\//,
  hooks: /^\/Users\/rushiparikh\/projects\/atom\/frontend-nextjs\/hooks\//
};

// Analyze components
const components = {
  agents: { files: [], lines_pct: 0, lines_covered: 0, lines_total: 0 },
  automations: { files: [], lines_pct: 0, lines_covered: 0, lines_total: 0 },
  canvas: { files: [], lines_pct: 0, lines_covered: 0, lines_total: 0 },
  auth: { files: [], lines_pct: 0, lines_covered: 0, lines_total: 0 },
  hooks: { files: [], lines_pct: 0, lines_covered: 0, lines_total: 0 }
};

// Critical hooks
const criticalHooks = ['useCanvasState.ts', 'useChatMemory.ts', 'useWebSocket.ts'];

const criticalFiles = [];
const zeroCoverageFiles = [];

for (const [filePath, data] of Object.entries(summary)) {
  if (filePath === 'total') continue;

  // Skip non-TypeScript files
  if (!filePath.match(/\.(ts|tsx)$/)) continue;

  const fileName = filePath.split('/').pop();

  // Check if file is in critical directories
  for (const [category, pattern] of Object.entries(criticalDirs)) {
    if (pattern.test(filePath)) {
      components[category].files.push({
        path: filePath.replace('/Users/rushiparikh/projects/atom/frontend-nextjs/', ''),
        coverage: data.lines.pct,
        lines_total: data.lines.total,
        lines_covered: data.lines.covered
      });
      components[category].lines_covered += data.lines.covered;
      components[category].lines_total += data.lines.total;

      // Check if it's a critical file
      if (category === 'hooks' && criticalHooks.includes(fileName)) {
        criticalFiles.push({
          path: filePath.replace('/Users/rushiparikh/projects/atom/frontend-nextjs/', ''),
          coverage: data.lines.pct,
          lines_total: data.lines.total
        });
      }

      if (data.lines.pct === 0) {
        zeroCoverageFiles.push({
          path: filePath.replace('/Users/rushiparikh/projects/atom/frontend-nextjs/', ''),
          lines_total: data.lines.total
        });
      }
      break;
    }
  }
}

// Calculate percentages for each component
for (const [key, component] of Object.entries(components)) {
  if (component.lines_total > 0) {
    component.lines_pct = ((component.lines_covered / component.lines_total) * 100).toFixed(2);
  }
}

// Calculate gap to 70%
const total = summary.total;
const currentLines = total.lines.covered;
const totalLines = total.lines.total;
const targetLines = Math.round(totalLines * 0.70);
const linesNeeded = targetLines - currentLines;

const baseline = {
  baseline: {
    timestamp: new Date().toISOString(),
    total_lines_pct: total.lines.pct,
    total_statements_pct: total.statements.pct,
    total_functions_pct: total.functions.pct,
    total_branches_pct: total.branches.pct,
    lines_covered: total.lines.covered,
    lines_total: total.lines.total
  },
  components: components,
  critical_files: criticalFiles.sort((a, b) => b.lines_total - a.lines_total),
  zero_coverage_files: zeroCoverageFiles.sort((a, b) => b.lines_total - a.lines_total).slice(0, 50),
  gap_to_70_percent: {
    lines_needed: Math.max(0, linesNeeded),
    current_lines: currentLines,
    target_lines: targetLines,
    percentage_points_needed: (70 - total.lines.pct).toFixed(2)
  }
};

fs.writeFileSync('coverage/baseline-254-analysis.json', JSON.stringify(baseline, null, 2));
console.log('Baseline analysis written to coverage/baseline-254-analysis.json');
console.log('Total Coverage:', total.lines.pct + '%');
console.log('Gap to 70%:', (70 - total.lines.pct).toFixed(2) + ' percentage points');
console.log('Lines needed:', Math.max(0, linesNeeded));
