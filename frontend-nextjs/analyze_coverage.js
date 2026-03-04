const fs = require('fs');
const data = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));

// Get total coverage first
console.log('=== TOTAL FRONTEND COVERAGE ===');
const total = data.total;
console.log('Lines: ' + total.lines.pct + '% (' + total.lines.covered + '/' + total.lines.total + ')');
console.log('Statements: ' + total.statements.pct + '% (' + total.statements.covered + '/' + total.statements.total + ')');
console.log('Functions: ' + total.functions.pct + '% (' + total.functions.covered + '/' + total.functions.total + ')');
console.log('Branches: ' + total.branches.pct + '% (' + total.branches.covered + '/' + total.branches.total + ')');

// Get all entries
const entries = Object.entries(data)
  .filter(([k]) => k !== 'total')
  .map(([k, v]) => ({ path: k.replace('/Users/rushiparikh/projects/atom/frontend-nextjs/', ''), pct: v.lines.pct, covered: v.lines.covered, total: v.lines.total }))
  .sort((a, b) => b.pct - a.pct);

// Top 60
console.log('\n=== TOP 60 MODULES BY LINE COVERAGE ===');
entries.slice(0, 60).forEach(e => console.log(e.path + ': ' + e.pct + '% (' + e.covered + '/' + e.total + ' lines)'));

// Bottom 60 (above 0%)
console.log('\n=== BOTTOM 60 MODULES (>0% COVERAGE) ===');
entries.filter(e => e.pct > 0).slice(-60).reverse().forEach(e => console.log(e.path + ': ' + e.pct + '% (' + e.covered + '/' + e.total + ' lines)'));

// Zero coverage modules
console.log('\n=== MODULES WITH 0% COVERAGE ===');
const zeroCoverage = entries.filter(e => e.pct === 0);
console.log('Total zero-coverage modules: ' + zeroCoverage.length);
zeroCoverage.slice(0, 30).forEach(e => console.log(e.path + ': ' + e.total + ' lines'));

// Directory-level analysis
console.log('\n=== DIRECTORY-LEVEL COVERAGE ===');
const dirs = {};
entries.forEach(e => {
  const dir = e.path.split('/')[0] || 'root';
  if (!dirs[dir]) dirs[dir] = { covered: 0, total: 0, files: 0 };
  dirs[dir].covered += e.covered;
  dirs[dir].total += e.total;
  dirs[dir].files++;
});
Object.entries(dirs).sort((a, b) => (b[1].covered/b[1].total) - (a[1].covered/a[1].total)).forEach(([dir, stats]) => {
  const pct = stats.total > 0 ? ((stats.covered / stats.total) * 100).toFixed(2) : 0;
  console.log(dir + '/: ' + pct + '% (' + stats.files + ' files, ' + stats.covered + '/' + stats.total + ' lines)');
});
