#!/usr/bin/env node

// Fix Test Props Script - Phase 299-07
//
// Automatically adds missing required props to test files by:
// 1. Identifying components rendered without required props
// 2. Creating defaultProps objects
// 3. Updating render() calls to spread defaultProps
//
// Usage:
//   node scripts/fix-test-props.js [test-file-pattern]
//
// Example:
//   node scripts/fix-test-props.js components/integrations/


const fs = require('fs');
const path = require('path');
const { glob } = require('glob');

// Common defaultProps patterns for integration components
const commonDefaultProps = {
  onConnect: 'jest.fn()',
  onDisconnect: 'jest.fn()',
  onError: 'jest.fn()',
  onSubmit: 'jest.fn()',
  onChange: 'jest.fn()',
  accessToken: "'test-token'",
  connected: 'false',
  isLoading: 'false',
};

function findTestFiles(pattern) {
  const files = glob.sync(pattern, {
    cwd: process.cwd(),
    absolute: true,
  });
  return files.filter(file => file.endsWith('.test.tsx') || file.endsWith('.test.ts'));
}

function analyzeTestFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  const issues = [];
  let inDescribeBlock = false;
  let currentDescribe = '';

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Track describe blocks
    if (line.includes('describe(')) {
      inDescribeBlock = true;
      const match = line.match(/describe\(['"](.+?)['"]/);
      if (match) currentDescribe = match[1];
    }

    // Find render() calls
    if (line.includes('render(') && !line.trim().startsWith('//')) {
      const renderMatch = line.match(/render\(<(\w+)/);
      if (renderMatch) {
        const componentName = renderMatch[1];

        // Check if props are provided
        const hasProps = line.includes('{') && line.includes('}');
        const hasSpread = line.includes('{...');

        if (!hasProps || !hasSpread) {
          issues.push({
            line: i + 1,
            componentName,
            text: line.trim(),
            describeBlock: currentDescribe,
          });
        }
      }
    }
  }

  return issues;
}

function generateDefaultProps(componentName, issues) {
  // Get unique component names from issues
  const uniqueComponents = [...new Set(issues.map(i => i.componentName))];

  const props = {};
  uniqueComponents.forEach(comp => {
    // Add common props based on component name patterns
    if (comp.includes('Integration')) {
      props[comp] = {
        onConnect: 'jest.fn()',
        onDisconnect: 'jest.fn()',
      };
    } else if (comp.includes('Form')) {
      props[comp] = {
        onSubmit: 'jest.fn()',
      };
    }
  });

  return props;
}

function fixTestFile(filePath, issues) {
  let content = fs.readFileSync(filePath, 'utf-8');
  const lines = content.split('\n');

  // Group issues by describe block
  const issuesByDescribe = {};
  issues.forEach(issue => {
    const key = issue.describeBlock || 'root';
    if (!issuesByDescribe[key]) {
      issuesByDescribe[key] = [];
    }
    issuesByDescribe[key].push(issue);
  });

  // Generate defaultProps for each describe block
  Object.entries(issuesByDescribe).forEach(([describeBlock, blockIssues]) => {
    const uniqueComponents = [...new Set(blockIssues.map(i => i.componentName))];

    // Skip if no components to fix
    if (uniqueComponents.length === 0) return;

    // Determine props needed
    const neededProps = new Set();
    uniqueComponents.forEach(comp => {
      if (comp.includes('Integration')) {
        neededProps.add('onConnect');
        neededProps.add('onDisconnect');
      }
      if (comp.includes('Form')) {
        neededProps.add('onSubmit');
      }
    });

    if (neededProps.size === 0) return;

    // Find the describe block location
    let insertLine = -1;
    for (let i = 0; i < lines.length; i++) {
      if (describeBlock === 'root' && lines[i].includes('describe(')) {
        insertLine = i + 1;
        break;
      } else if (describeBlock !== 'root' && lines[i].includes(`describe('${describeBlock}'`)) {
        insertLine = i + 1;
        break;
      }
    }

    if (insertLine === -1) return;

    // Generate defaultProps declaration
    const propsArray = Array.from(neededProps).map(prop =>
      `    ${prop}: jest.fn(),`
    );
    const defaultPropsCode = `  const defaultProps = {\n${propsArray.join('\n')}\n  };\n`;

    // Insert defaultProps after describe block
    // Check if beforeEach already exists
    let inserted = false;
    if (lines[insertLine].includes('beforeEach(')) {
      lines.splice(insertLine, 0, defaultPropsCode);
      inserted = true;
    } else {
      lines.splice(insertLine, 0, defaultPropsCode);
      inserted = true;
    }

    // Now update render() calls to use defaultProps
    for (let i = insertLine; i < lines.length; i++) {
      const line = lines[i];
      if (line.includes('render(<') && !line.includes('...defaultProps')) {
        const renderMatch = line.match(/render\(<(\w+)(\s+|\/>)/);
        if (renderMatch) {
          const componentName = renderMatch[1];
          const needsProps = uniqueComponents.includes(componentName);

          if (needsProps) {
            // Replace render(<Component />) with render(<Component {...defaultProps} />)
            lines[i] = line.replace(
              /render\(<(\w+)(\s*)/,
              'render(<$1 {...defaultProps}$2'
            );
          }
        }
      }
    }
  });

  return lines.join('\n');
}

function main() {
  const pattern = process.argv[2] || 'components/**/*.test.tsx';
  const files = findTestFiles(pattern);

  console.log(`Found ${files.length} test files to analyze`);

  let fixedCount = 0;
  let issueCount = 0;

  files.forEach(file => {
    const issues = analyzeTestFile(file);
    if (issues.length > 0) {
      console.log(`\n${path.relative(process.cwd(), file)}:`);
      issues.forEach(issue => {
        console.log(`  Line ${issue.line}: ${issue.componentName}`);
      });
      issueCount += issues.length;

      // Fix the file
      const fixed = fixTestFile(file, issues);
      fs.writeFileSync(file, fixed, 'utf-8');
      fixedCount++;
    }
  });

  console.log(`\n✅ Fixed ${fixedCount} files with ${issueCount} issues`);
}

if (require.main === module) {
  main();
}

module.exports = { findTestFiles, analyzeTestFile, fixTestFile };
