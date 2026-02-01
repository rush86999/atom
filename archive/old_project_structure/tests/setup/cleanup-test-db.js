const mongoose = require('mongoose');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Test database configuration
const TEST_DB_NAME = process.env.TEST_DB_NAME || 'atom_test';
const DATABASE_URL = process.env.DATABASE_URL || `postgresql://localhost:5432/${TEST_DB_NAME}`;

async function cleanupTestDatabase() {
  console.log('🧹 Cleaning up test database...');

  try {
    // Remove test user data files
    const testDataPath = path.join(__dirname, '../fixtures/test-users.json');
    if (fs.existsSync(testDataPath)) {
      fs.unlinkSync(testDataPath);
      console.log('🗑️  Removed test users file');
    }

    // Clean up Allure test results
    const resultsDir = path.join(__dirname, '../results');
    if (fs.existsSync(resultsDir)) {
      fs.rmSync(resultsDir, { recursive: true, force: true });
      console.log('🗑️  Cleaned up test results directory');
    }

    // Drop test database
    if (DATABASE_URL.includes('postgresql')) {
      try {
        execSync(`dropdb ${TEST_DB_NAME}`, { stdio: 'ignore' });
        console.log(`🗑️  Dropped test database: ${TEST_DB_NAME}`);
      } catch (error) {
        console.log('ℹ️  Test database might not exist or could not be dropped');
      }
    }

    // Clean up any temporary files
    const tempDirs = ['screenshots', 'videos', 'downloads'];
    for (const dir of tempDirs) {
      const fullPath = path.join(__dirname, '../', dir);
      if (fs.existsSync(fullPath)) {
        fs.rmSync(fullPath, { recursive: true, force: true });
        console.log(`🗑️  Cleaned up temporary directory: ${dir}`);
      }
    }

    console.log('✅ Test database cleanup complete');
  } catch (error) {
    console.error('❌ Error during cleanup:', error);
    // Don't throw on cleanup errors - continue
  }
}

// Run cleanup if called directly
if (require.main === module) {
  cleanupTestDatabase()
    .then(() => process.exit(0))
    .catch(error => {
      console.error(error);
      process.exit(1);
    });
}

module.exports = { cleanupTestDatabase };
