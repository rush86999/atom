#!/usr/bin/env node

/**
 * Fix import/export mismatches in test files
 *
 * Scans for patterns like:
 *   import { ComponentName } from './Component'
 * When the actual export is:
 *   export default ComponentName
 *
 * Usage: node scripts/fix-imports-299-11.js
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// ANSI color codes
const GREEN = '\x1b[32m';
const RED = '\x1b[31m';
const YELLOW = '\x1b[33m';
const RESET = '\x1b[0m';

function log(message, color = RESET) {
  console.log(`${color}${message}${RESET}`);
}

// Find all test files
function findTestFiles() {
  const result = execSync(
    'find components hooks lib -name "*.test.tsx" -o -name "*.test.ts" 2>/dev/null',
    { encoding: 'utf8', cwd: process.cwd() }
  );
  return result.split('\n').filter(Boolean);
}

// Check if a component uses default export
function isDefaultExport(componentPath) {
  try {
    const content = fs.readFileSync(componentPath, 'utf8');

    // Check for default export
    if (/export default\s+[\w_]+/.test(content)) {
      return { isDefault: true, content };
    }

    // Check for named exports
    const namedExports = content.match(/export\s+(const|function|class|interface|type)\s+(\w+)/g);
    if (namedExports) {
      const exports = namedExports.map(e => e.match(/export\s+(?:const|function|class|interface|type)\s+(\w+)/)[1]);
      return { isDefault: false, exports, content };
    }

    return { isDefault: false, exports: [], content };
  } catch (error) {
    log(`  Error reading ${componentPath}: ${error.message}`, RED);
    return null;
  }
}

// Fix import statement in test file
function fixImportStatement(testFile, componentFile, componentName) {
  try {
    let content = fs.readFileSync(testFile, 'utf8');
    const originalContent = content;

    // Pattern 1: Named import from component file (should be default import)
    const pattern1 = new RegExp(
      `import\\s*{\\s*${componentName}\\s*}\\s*from\\s*['"](.+/?)${componentName}['"]`,
      'g'
    );

    if (pattern1.test(content)) {
      log(`  Found named import for ${componentName} (likely should be default)`, YELLOW);

      content = content.replace(
        pattern1,
        `import ${componentName} from '$1${componentName}'`
      );

      if (content !== originalContent) {
        fs.writeFileSync(testFile, content, 'utf8');
        log(`  ✓ Fixed import in ${testFile}`, GREEN);
        return true;
      }
    }

    return false;
  } catch (error) {
    log(`  Error fixing ${testFile}: ${error.message}`, RED);
    return false;
  }
}

// Main execution
async function main() {
  log('🔍 Scanning for import/export mismatches...\n', YELLOW);

  const testFiles = findTestFiles();
  log(`Found ${testFiles.length} test files\n`);

  let fixedCount = 0;
  let checkedCount = 0;

  for (const testFile of testFiles) {
    // Read test file and extract import statements
    try {
      const content = fs.readFileSync(testFile, 'utf8');

      // Find imports from local files (not node_modules)
      const importRegex = /import\s*{([^}]+)}\s*from\s*['"]\.\.\/([^'"]+)['"]/g;
      let match;
      let hasChanges = false;

      while ((match = importRegex.exec(content)) !== null) {
        const [, imports, relativePath] = match;
        const importNames = imports.split(',').map(s => s.trim().split(' as ')[0]);

        // Resolve component file path
        const testDir = path.dirname(testFile);
        const componentPath = path.resolve(testDir, relativePath);

        if (!fs.existsSync(componentPath)) {
          continue;
        }

        checkedCount++;

        // Check export type
        const exportInfo = isDefaultExport(componentPath);
        if (!exportInfo) continue;

        // For each named import, check if it's actually a default export
        for (const importName of importNames) {
          if (exportInfo.isDefault) {
            // This is a named import of a default export - fix it
            const fixed = fixImportStatement(testFile, componentPath, importName);
            if (fixed) {
              hasChanges = true;
              fixedCount++;
            }
          }
        }
      }
    } catch (error) {
      // Skip files that can't be read
    }
  }

  log(`\n✅ Summary:`, GREEN);
  log(`  Checked: ${checkedCount} imports`);
  log(`  Fixed:   ${fixedCount} import statements`);
  log(`  Files:   ${testFiles.length} test files scanned\n`);

  if (fixedCount > 0) {
    log('📝 Please review the changes and commit them.', YELLOW);
    log('   Run tests to verify fixes: npm test -- --no-coverage\n', YELLOW);
  } else {
    log('✓ No import/export mismatches found!', GREEN);
  }
}

main().catch(error => {
  log(`\n❌ Error: ${error.message}`, RED);
  process.exit(1);
});
