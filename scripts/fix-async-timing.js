#!/usr/bin/env node

// Fix Async Timing Script - Phase 299-07 Batch 4
//
// Automatically adds waitFor() wrappers to async assertions to fix timing issues.
//
// Usage:
//   node scripts/fix-async-timing.js

const fs = require('fs');
const path = require('path');
const { glob } = require('glob');

function findTestFiles() {
  const files = glob.sync('**/*.test.tsx', {
    cwd: process.cwd(),
    absolute: true,
    ignore: ['**/node_modules/**', '**/dist/**'],
  });
  return files;
}

function fixTestFile(filePath) {
  let content = fs.readFileSync(filePath, 'utf-8');
  const original = content;

  // Skip if already using waitFor extensively
  if ((content.match(/waitFor\(/g) || []).length > 5) {
    return { fixed: false, reason: 'already using waitFor' };
  }

  let changes = 0;

  // Pattern 1: screen.getByText...toBeInTheDocument() without waitFor
  // Look for this pattern in async functions or after userEvent.click/fireEvent
  const lines = content.split('\n');
  const newLines = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const prevLine = i > 0 ? lines[i - 1] : '';
    const prevPrevLine = i > 1 ? lines[i - 2] : '';

    // Check if this is an assertion that needs waitFor
    const needsWaitFor =
      (line.includes('getByText') || line.includes('getByRole') || line.includes('getByTestId') || line.includes('getByLabelText')) &&
      (line.includes('.toBeInTheDocument()') || line.includes('.toBeVisible()')) &&
      !line.includes('waitFor') &&
      !line.includes('findBy') && // findBy already waits
      !line.trim().startsWith('//'); // not a comment

    // Check if this assertion comes after an async action
    const hasAsyncContext =
      prevLine.includes('userEvent.click') ||
      prevLine.includes('userEvent.type') ||
      prevLine.includes('fireEvent') ||
      prevLine.includes('waitFor') ||
      prevPrevLine.includes('userEvent.click') ||
      prevPrevLine.includes('userEvent.type') ||
      prevPrevLine.includes('fireEvent') ||
      line.trim().startsWith('await');

    if (needsWaitFor && hasAsyncContext) {
      // Add waitFor wrapper
      const indent = line.match(/^\s*/)[0];
      const assertion = line.trim();
      
      // Extract the expect(...) part
      const expectMatch = assertion.match(/expect\((.+)\)\.(toBeInTheDocument|toBeVisible)\(\)/);
      if (expectMatch) {
        const query = expectMatch[1];
        const matcher = expectMatch[2];
        
        newLines.push(`${indent}await waitFor(() => {`);
        newLines.push(`${indent}  ${assertion}`);
        newLines.push(`${indent}}, { timeout: 5000 });`);
        changes++;
        continue;
      }
    }

    newLines.push(line);
  }

  if (changes > 0) {
    const newContent = newLines.join('\n');
    
    // Make sure waitFor is imported
    if (newContent.includes('waitFor(') && !newContent.includes('waitFor') && !newContent.includes('@testing-library/react')) {
      // Add waitFor to existing import
      newContent = newContent.replace(
        /import\s+{\s*([^}]+)}\s+from\s+['"]@testing-library\/react['"]/,
        'import { $1, waitFor } from \'@testing-library/react\''
      );
    } else if (newContent.includes('waitFor(') && !newContent.includes('waitFor')) {
      // Add waitFor to import from test-utils
      newContent = newContent.replace(
        /import\s+{\s*([^}]+)}\s+from\s+['"]\.\.\/\.\.\/tests\/test-utils['"]/,
        'import { $1, waitFor } from \'../../../tests/test-utils\''
      );
      newContent = newContent.replace(
        /import\s+{\s*([^}]+)}\s+from\s+['"]\.\.\/\.\.\/\.\.\/tests\/test-utils['"]/,
        'import { $1, waitFor } from \'../../../../tests/test-utils\''
      );
    }

    fs.writeFileSync(filePath, newContent, 'utf-8');
    return { fixed: true, changes };
  }

  return { fixed: false, reason: 'no timing issues found' };
}

function main() {
  const files = findTestFiles();
  console.log(`Found ${files.length} test files to check`);

  let fixedCount = 0;
  let totalChanges = 0;

  files.forEach(file => {
    try {
      const result = fixTestFile(file);
      if (result.fixed) {
        console.log(`✅ Fixed: ${path.relative(process.cwd(), file)} (${result.changes} changes)`);
        fixedCount++;
        totalChanges += result.changes;
      }
    } catch (error) {
      console.error(`❌ Error fixing ${path.relative(process.cwd(), file)}: ${error.message}`);
    }
  });

  console.log(`\n📊 Summary:`);
  console.log(`  ✅ Fixed: ${fixedCount} files`);
  console.log(`  🔧 Total changes: ${totalChanges}`);
}

if (require.main === module) {
  main();
}

module.exports = { fixTestFile };
