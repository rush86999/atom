#!/usr/bin/env node
/**
 * Coverage Trend Tracker - Phase 130-06
 * Tracks coverage trends over time (Node.js version of backend pattern)
 * Usage: node scripts/coverage-trend-tracker.js [update|report|html]
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const COVERAGE_FILE = path.join(__dirname, '../coverage/coverage-summary.json');
const TREND_FILE = path.join(__dirname, '../coverage-trend.jsonl');
const REPORT_DIR = path.join(__dirname, '../coverage/reports');

function loadCoverage() {
  if (!fs.existsSync(COVERAGE_FILE)) {
    return null;
  }
  return JSON.parse(fs.readFileSync(COVERAGE_FILE, 'utf8'));
}

function loadTrends() {
  if (!fs.existsSync(TREND_FILE)) {
    return [];
  }
  return fs.readFileSync(TREND_FILE, 'utf8')
    .trim()
    .split('\n')
    .map(line => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

function saveTrend(data) {
  const line = JSON.stringify(data) + '\n';
  fs.appendFileSync(TREND_FILE, line);
}

function updateTrend() {
  const coverage = loadCoverage();
  if (!coverage) {
    console.error('Coverage file not found. Run tests first.');
    process.exit(1);
  }

  const sha = execSync('git rev-parse HEAD').toString().trim();
  const timestamp = new Date().toISOString();
  const branch = execSync('git rev-parse --abbrev-ref HEAD').toString().trim();
  const message = execSync('git log -1 --pretty=%B').toString().trim();

  const trendEntry = {
    timestamp,
    sha,
    branch,
    message: message.split('\n')[0], // First line only
    coverage: {
      total: coverage.total?.lines?.pct || 0,
      modules: extractModuleCoverage(coverage),
    },
  };

  saveTrend(trendEntry);
  console.log(`Trend updated: ${trendEntry.coverage.total}% (${sha.slice(0, 7)})`);
}

function extractModuleCoverage(coverage) {
  const modules = {};
  for (const [filepath, metrics] of Object.entries(coverage)) {
    if (filepath === 'total') continue;

    const moduleKey = filepath.split('/')[1] || 'root';
    if (!modules[moduleKey]) {
      modules[moduleKey] = { covered: 0, total: 0 };
    }
    modules[moduleKey].covered += metrics.lines.covered;
    modules[moduleKey].total += metrics.lines.total;
  }

  const result = {};
  for (const [key, data] of Object.entries(modules)) {
    result[key] = data.total > 0 ? Math.round((data.covered / data.total) * 100) : 0;
  }
  return result;
}

function generateReport() {
  const trends = loadTrends();
  if (trends.length === 0) {
    console.log('No trend data available.');
    return;
  }

  const latest = trends[trends.length - 1];
  const previous = trends.length > 1 ? trends[trends.length - 2] : null;

  console.log('\n=== COVERAGE TREND REPORT ===\n');
  console.log(`Entries: ${trends.length}`);
  console.log(`Latest: ${latest.timestamp}`);
  console.log(`Branch: ${latest.branch}\n`);

  console.log('Current Coverage:');
  console.log(`  Total: ${latest.coverage.total}%`);
  for (const [module, pct] of Object.entries(latest.coverage.modules)) {
    console.log(`  ${module}: ${pct}%`);
  }

  if (previous) {
    const delta = latest.coverage.total - previous.coverage.total;
    const symbol = delta > 0 ? '+' : '';
    console.log(`\nChange from previous: ${symbol}${delta}%`);
  }

  // Calculate 7-day trend
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const weekEntries = trends.filter(t => new Date(t.timestamp) > weekAgo);
  if (weekEntries.length > 1) {
    const weekDelta = weekEntries[weekEntries.length - 1].coverage.total - weekEntries[0].coverage.total;
    const symbol = weekDelta > 0 ? '+' : '';
    console.log(`7-day trend: ${symbol}${weekDelta}% (${weekEntries.length} commits)`);
  }
}

function generateHtmlReport() {
  const trends = loadTrends();
  if (!fs.existsSync(REPORT_DIR)) {
    fs.mkdirSync(REPORT_DIR, { recursive: true });
  }

  const reportPath = path.join(REPORT_DIR, 'trend.html');
  const html = generateTrendHtml(trends);
  fs.writeFileSync(reportPath, html);
  console.log(`HTML report generated: ${reportPath}`);
}

function generateTrendHtml(trends) {
  const dataPoints = trends.map(t => ({
    date: new Date(t.timestamp).toISOString().split('T')[0],
    coverage: t.coverage.total,
  }));

  return `<!DOCTYPE html>
<html>
<head>
  <title>Frontend Coverage Trend</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body { font-family: Arial, sans-serif; margin: 20px; }
    h1 { color: #333; }
    .chart-container { position: relative; height: 400px; width: 800px; }
  </style>
</head>
<body>
  <h1>Frontend Coverage Trend</h1>
  <div class="chart-container">
    <canvas id="trendChart"></canvas>
  </div>
  <script>
    const ctx = document.getElementById('trendChart').getContext('2d');
    new Chart(ctx, {
      type: 'line',
      data: {
        labels: ${JSON.stringify(dataPoints.map(d => d.date))},
        datasets: [{
          label: 'Coverage %',
          data: ${JSON.stringify(dataPoints.map(d => d.coverage))},
          borderColor: 'rgb(75, 192, 192)',
          backgroundColor: 'rgba(75, 192, 192, 0.2)',
          tension: 0.1,
          fill: true
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: {
            min: 0,
            max: 100,
            title: {
              display: true,
              text: 'Coverage %'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Date'
            }
          }
        },
        plugins: {
          legend: {
            display: true,
            position: 'top'
          }
        }
      }
    });
  </script>
</body>
</html>`;
}

// CLI
const command = process.argv[2] || 'update';

switch (command) {
  case 'update':
    updateTrend();
    break;
  case 'report':
    generateReport();
    break;
  case 'html':
    generateHtmlReport();
    break;
  default:
    console.log('Usage: node coverage-trend-tracker.js [update|report|html]');
    process.exit(1);
}
