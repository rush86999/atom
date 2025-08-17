const mongoose = require('mongoose');
const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
require('dotenv').config();

// Test database configuration
const TEST_DB_NAME = process.env.TEST_DB_NAME || 'atom_test';
const DATABASE_URL = process.env.DATABASE_URL || `postgresql://localhost:5432/${TEST_DB_NAME}`;

async function setupTestDatabase() {
  console.log('🗄️  Setting up test database...');

  try {
    // Create test database if using PostgreSQL
    if (DATABASE_URL.includes('postgresql')) {
      try {
        execSync(`createdb ${TEST_DB_NAME}`, { stdio: 'ignore' });
      } catch (error) {
        // Database might already exist, drop and recreate
        try {
          execSync(`dropdb ${TEST_DB_NAME}`, { stdio: 'ignore' });
          execSync(`createdb ${TEST_DB_NAME}`, { stdio: 'ignore' });
        } catch (dropError) {
          console.log('⚠️  Could not recreate database, may already exist');
        }
      }
    }

    // Initialize Prisma migrations if available
    const prismaExists = fs.existsSync(path.join(process.cwd(), 'prisma'));
    if (prismaExists) {
      console.log('🔄 Running Prisma migrations...');
      execSync('npx prisma migrate reset --force', { stdio: 'inherit' });
      execSync('npx prisma db seed', { stdio: 'inherit' });
    }

    // Create test users for personas
    const testUsers = {
      alex: {
        id: 'test-alex-001',
        name: 'Alex Chen',
        email: 'alex.test@example.com',
        persona: 'busy_professional'
      },
      maria: {
        id: 'test-maria-001',
        name: 'Maria Rodriguez',
        email: 'maria.test@example.com',
        persona: 'financial_optimizer'
      },
      ben: {
        id: 'test-ben-001',
        name: 'Ben Carter',
        email: 'ben.test@example.com',
        persona: 'solopreneur'
      }
    };

    // Save test users to file for other test scripts
    const testDataPath = path.join(__dirname, '../fixtures/test-users.json');
    fs.writeFileSync(testDataPath, JSON.stringify(testUsers, null, 2));

    console.log('✅ Test database setup complete');
    return testUsers;
  } catch (error) {
    console.error('❌ Error setting up test database:', error);
    throw error;
  }
}

// Run setup if called directly
if (require.main === module) {
  setupTestDatabase()
    .then(() => process.exit(0))
    .catch(error => {
      console.error(error);
      process.exit(1);
    });
}

module.exports = { setupTestDatabase };
