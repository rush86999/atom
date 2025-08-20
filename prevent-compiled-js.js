#!/usr/bin/env node
/**
 * Git commit hook to prevent compiled JavaScript files from being committed
 * Ensures we only commit TypeScript source files (.ts) and exclude compiled .js
 */

const fs = require('fs');
const path = require('path');

const compiledPatterns = [
  '**/lib/**/*.js',
  '**/src/**/*.js',
  '**/functions/**/*.js',
  '**/components/**/*.js',
  '**/utils/**/*.js',
  '**/services/**/*.js',
  '**/hooks/**/*.js',
  '**/build/**/*.js',
];

const allowedPatterns = [
  '!**/next.config.js',
  '!**/jest.config.js',
  '!**/tailwind.config.js',
  '!**/postcss.config.js',
  '!**/babel.config.js',
  '!**/webpack.config.js',
  '!**/eslint.config.js',
  '!**/.eslintrc.js',
  '!**/prettier.config.js',
];

function matchesPattern(filePath, patterns) {
  const relPath = path.relative(process.cwd(), filePath);

  // Check direct matches
  for (const pattern of compiledPatterns) {
    if (pattern.includes('**/')) {
      const regex = new RegExp(pattern.replace('**/', '.*').replace('*', '[^/]*'));
      if (regex.test(relPath)) {
        // Check if corresponding .ts file exists
        const tsPath = relPath.replace(/\.js$/, '.ts');
        if (fs.existsSync(tsPath)) {
          return true;
        }

        // Check for .tsx file
        const tsxPath = relPath.replace(/\.js$/, '.tsx');
        if (fs.existsSync(tsxPath)) {
          return true;
        }
      }
    }
  }
  return false;
}

async function checkPreCommit() {
  console.log('🚫 Checking for compiled JavaScript files...');

  try {
    const { execSync } = require('child_process');
    const stagedFiles = execSync('git diff --cached --name-only', { encoding: 'utf8' }).split('\n').filter(Boolean);

    const violations = [];

    for (const file of stagedFiles) {
      if (file.endsWith('.js') && matchesPattern(file, compiledPatterns)) {
        violations.push(file);
      }
    }

    if (violations.length > 0) {
      console.error('\n❌ ERROR: Found compiled JavaScript files being committed:');
      violations.forEach(v => console.error(`   ${v}`));

      console.error('\n📝 These files appear to be compiled TypeScript outputs.');
      console.error('   Ensure you are committing the original .ts files instead.');
      console.error('   You can remove these generated files with:');
      console.error('   rm '.concat(...violations.slice(0, 5)));
      console.error('\n   If these are legitimate source files, update .gitignore accordingly.\n');

      process.exit(1);
    }

    console.log('✅ No compiled JavaScript files found.');
    process.exit(0);

  } catch (error) {
    console.error('❌ Error checking pre-commit file:', error.message);
    process.exit(1);
  }
}

// Run if called directly
if (require.main === module) {
  checkPreCommit();
}

module.exports = { checkPreCommit, matchesPattern };
