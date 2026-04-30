const fs = require('fs');
const path = require('path');

const summary = JSON.parse(fs.readFileSync('coverage/coverage-summary.json', 'utf8'));

// Files with NO test files
const filesWithNoTests = [];
for (const [filepath, data] of Object.entries(summary)) {
  if (filepath === 'total') continue;

  // Check if test file exists
  const dirname = path.dirname(filepath);
  const basename = path.basename(filepath).replace('.tsx', '').replace('.ts', '');
  const testFilePath = path.join(dirname, '__tests__', basename + '.test.tsx');
  const altTestFilePath = filepath.replace('.tsx', '.test.tsx').replace('.ts', '.test.ts');

  const hasTest = fs.existsSync(testFilePath) || fs.existsSync(altTestFilePath);

  if (!hasTest) {
    const uncoveredLines = (data.lines?.total || 0) - (data.lines?.covered || 0);
    if (uncoveredLines > 50) {
      filesWithNoTests.push({
        path: filepath,
        uncoveredLines,
        totalLines: data.lines?.total || 0,
        coverage: data.lines?.pct || 0
      });
    }
  }
}

filesWithNoTests.sort((a, b) => b.uncoveredLines - a.uncoveredLines);

console.log('=== TOP 30 FILES WITH NO TESTS AND MOST UNCOVERED LINES ===');
filesWithNoTests.slice(0, 30).forEach((f, i) => {
  const shortPath = f.path.replace('/Users/rushiparikh/projects/atom/frontend-nextjs/', '');
  console.log(`${i+1}. ${shortPath}`);
  console.log(`   Uncovered: ${f.uncoveredLines}/${f.totalLines} lines (${f.coverage}% coverage)`);
});
