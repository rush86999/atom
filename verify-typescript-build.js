```#!/usr/bin/env node
/**
 * TypeScript Build Verification Script
 * Ensures that the codebase can build correctly from TypeScript sources
 */

const fs = require('fs');
const path = require('path');
const { exec, execSync } = require('child_process');

console.log('🔧 Verifying TypeScript build integrity...\n');

const checks = [
  { name: 'TypeScript CLI', command: 'npx tsc --version' },
  { name: 'Package Configuration', file: './package.json', type: 'file' },
  { name: 'TS Config', file: './tsconfig.json', type: 'file' },
];

async function runChecks() {
  let failures = 0;

  console.log('📋 Initial checks:');

  for (const check of checks) {
    if (check.command) {
      try {
        const output = execSync(check.command, { encoding: 'utf8', stdio: 'pipe' });
        console.log(`✅ ${check.name}: ${output.trim()}`);
      } catch (error) {
        console.log(`❌ ${check.name}: ${error.message}`);
        failures++;
      }
    } else if (check.file) {
      if (fs.existsSync(check.file)) {
        console.log(`✅ ${check.name}: Found`);
      } else {
        console.log(`❌ ${check.name}: Missing`);
        failures++;
      }
    }
  }

  console.log('\n🔍 Checking TypeScript compilation...');

  try {
    // Build TypeScript
    console.log('Running TypeScript build...');
    execSync('npx tsc --build --force', { stdio: 'inherit' });
    console.log('✅ TypeScript compilation successful');
  } catch (error) {
    console.error('\n❌ TypeScript compilation failed');
    console.error('Error:', error.message);
    failures++;
  }

  console.log('\n📊 Summary:');

  if (failures === 0) {
    console.log('🎉 All checks passed! TypeScript codebase is ready.');
    console.log('📦 Your build outputs will be generated from TypeScript sources.');
  } else {
    console.log(`⚠️  Found ${failures} issues. Please fix before continuing.`);
    if (failures > 1 || !fs.existsSync('./tsconfig.json')) {
      console.log('\n💡 Suggestions:');
      console.log('   1. Ensure TypeScript is properly installed: npm install -D typescript');
      console.log('   2. Add tsconfig.json to configure TypeScript compilation');
      console.log('   3. Check package.json for build scripts');
    }
  }

  return failures === 0;
}

// If run directly, execute the checks
if (require.main === module) {
  runChecks().then(success => {
    if (!success) {
      process.exit(1);
    }
  }).catch(error => {
    console.error('❌ Error running verification:', error);
    process.exit(1);
  });
}

module.exports = { runChecks };
