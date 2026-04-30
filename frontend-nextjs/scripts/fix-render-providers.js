#!/usr/bin/env node

/**
 * Fix Render Providers Script - Phase 299-07 Batch 1
 *
 * Automatically replaces render() with renderWithProviders() in test files.
 * This fixes "Element Not Found" errors caused by missing context providers.
 */

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

  // Skip if already using renderWithProviders
  if (content.includes('renderWithProviders')) {
    return { fixed: false, reason: 'already using renderWithProviders' };
  }

  // Skip if importing from test-utils
  if (content.includes('../tests/test-utils') || content.includes('@/tests/test-utils')) {
    return { fixed: false, reason: 'already importing from test-utils' };
  }

  // Replace import statement
  // Pattern 1: import { render } from '@testing-library/react'
  if (content.includes("import { render } from '@testing-library/react'")) {
    content = content.replace(
      "import { render } from '@testing-library/react'",
      "import { renderWithProviders } from '../../tests/test-utils'"
    );
  } else if (content.includes('import { render } from "@testing-library/react"')) {
    content = content.replace(
      'import { render } from "@testing-library/react"',
      'import { renderWithProviders } from "../../tests/test-utils"'
    );
  }

  // Pattern 2: import { render, screen } from '@testing-library/react'
  else if (content.includes("import { render, screen } from '@testing-library/react'")) {
    content = content.replace(
      "import { render, screen } from '@testing-library/react'",
      "import { renderWithProviders, screen } from '../../tests/test-utils'"
    );
  } else if (content.includes('import { render, screen } from "@testing-library/react"')) {
    content = content.replace(
      'import { render, screen } from "@testing-library/react"',
      'import { renderWithProviders, screen } from "../../tests/test-utils"'
    );
  }

  // Pattern 3: import { render, screen, waitFor } from '@testing-library/react'
  else if (content.includes("import { render, screen, waitFor } from '@testing-library/react'")) {
    content = content.replace(
      "import { render, screen, waitFor } from '@testing-library/react'",
      "import { renderWithProviders, screen, waitFor } from '../../tests/test-utils'"
    );
  } else if (content.includes('import { render, screen, waitFor } from "@testing-library/react"')) {
    content = content.replace(
      'import { render, screen, waitFor } from "@testing-library/react"',
      'import { renderWithProviders, screen, waitFor } from "../../tests/test-utils"'
    );
  }

  // Pattern 4: import * as testingLibrary from '@testing-library/react'
  else if (content.match(/import\s+\*\s+as\s+\w+\s+from\s+['"]@testing-library\/react['"]/)) {
    return { fixed: false, reason: 'using namespace import (manual fix needed)' };
  }

  // If no render import found, skip
  if (!content.includes('renderWithProviders') && content.includes("from '@testing-library/react'")) {
    return { fixed: false, reason: 'no render import found' };
  }

  // Now replace render( with renderWithProviders(
  content = content.replace(/\brender\(/g, 'renderWithProviders(');

  // Calculate relative path to test-utils
  const relativePath = path.relative(path.dirname(filePath), path.join(process.cwd(), 'tests/test-utils.tsx'));
  const normalizedPath = relativePath.replace(/\.tsx$/, '').replace(/\\/g, '/');

  // Fix the import path to be correct
  content = content.replace(/from ['"]\.\.\/\.\.\/tests\/test-utils['"]/g, `from '${normalizedPath}'`);
  content = content.replace(/from ['"]\.\.\/\.\.\/\.\.\/tests\/test-utils['"]/g, `from '${normalizedPath}'`);

  if (content !== original) {
    fs.writeFileSync(filePath, content, 'utf-8');
    return { fixed: true, changes: 1 };
  }

  return { fixed: false, reason: 'no changes needed' };
}

function main() {
  const files = findTestFiles();
  console.log(`Found ${files.length} test files to check`);

  let fixedCount = 0;
  let skippedCount = 0;
  const errors = [];

  files.forEach(file => {
    try {
      const result = fixTestFile(file);
      if (result.fixed) {
        console.log(`✅ Fixed: ${path.relative(process.cwd(), file)}`);
        fixedCount++;
      } else {
        skippedCount++;
      }
    } catch (error) {
      console.error(`❌ Error fixing ${path.relative(process.cwd(), file)}: ${error.message}`);
      errors.push({ file, error: error.message });
    }
  });

  console.log(`\n📊 Summary:`);
  console.log(`  ✅ Fixed: ${fixedCount} files`);
  console.log(`  ⏭️  Skipped: ${skippedCount} files`);
  console.log(`  ❌ Errors: ${errors.length} files`);

  if (errors.length > 0) {
    console.log('\n❌ Errors:');
    errors.forEach(({ file, error }) => {
      console.log(`  ${file}: ${error}`);
    });
  }
}

if (require.main === module) {
  main();
}

module.exports = { fixTestFile };
