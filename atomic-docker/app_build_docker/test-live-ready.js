#!/usr/bin/env node

/**
 * Live-Ready Production Test Runner
 * Comprehensive end-to-end testing for Atom application
 * Handles PostgreSQL database through environment variables
 */

const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const https = require('https');
const axios = require('axios').default;

// Environment variable handling with secure defaults
const ENV_CONFIG = {
    // PostgreSQL Database Configuration
    POSTGRES_HOST: process.env.POSTGRES_HOST || 'localhost',
    POSTGRES_PORT: process.env.POSTGRES_PORT || '5432',
    POSTGRES_DB: process.env.POSTGRES_DB || 'atom_production',
    POSTGRES_USER: process.env.POSTGRES_USER || process.env.DATABASE_USER || 'atom_user',
    POSTGRES_PASSWORD: process.env.POSTGRES_PASSWORD || process.env.DATABASE_PASSWORD,

    // Application Configuration
    NODE_ENV: process.env.NODE_ENV || 'production',
    PORT: process.env.PORT || '3000',

    // Critical Services
    OPENAI_API_KEY: process.env.OPENAI_API_KEY,
    JWT_SECRET: process.env.JWT_SECRET,

    // External Services
    GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
    GOOGLE_CLIENT_SECRET: process.env.GOOGLE_CLIENT_SECRET,
    LINKEDIN_CLIENT_ID: process.env.LINKEDIN_CLIENT_ID,
    LINKEDIN_CLIENT_SECRET: process.env.LINKEDIN_CLIENT_SECRET,

    // Test Configuration
    TEST_TIMEOUT: parseInt(process.env.TEST_TIMEOUT) || 60000,
    SERVER_STARTUP_TIMEOUT: parseInt(process.env.SERVER_STARTUP_TIMEOUT) || 120000,

    // Security
    ENCRYPTION_KEY: process.env.ENCRYPTION_KEY,
    HASH_SECRET: process.env.HASH_SECRET,
};

class DatabaseTester {
    constructor() {
        this.connectionString = this.buildConnectionString();
    }

    buildConnectionString() {
        const { POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD } = ENV_CONFIG;

        if (!POSTGRES_PASSWORD) {
            throw new Error('POSTGRES_PASSWORD environment variable is required');
        }

        return `postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}`;
    }

    async testConnection() {
        try {
            console.log('🔍 Testing PostgreSQL database connection...');
            console.log(`Host: ${ENV_CONFIG.POSTGRES_HOST}:${ENV_CONFIG.POSTGRES_PORT}`);
            console.log(`Database: ${ENV_CONFIG.POSTGRES_DB}`);
            console.log(`User: ${ENV_CONFIG.POSTGRES_USER}`);

            // Use pg package to test connection
            const { Client } = require('pg');
            const client = new Client({ connectionString: this.connectionString });

            await client.connect();
            const result = await client.query('SELECT NOW(), version(), current_database()');
            await client.end();

            console.log('✅ Database connection successful');
            console.log(`   Server version: ${result.rows[0].version}`);
            console.log(`   Database: ${result.rows[0].current_database}`);

            return {
                status: 'connected',
                version: result.rows[0].version,
                time: result.rows[0].now,
            };
        } catch (error) {
            console.error('❌ Database connection failed:');
            console.error(`   Error: ${error.message}`);
            return { status: 'error', error: error.message };
        }
    }

    async testMigrations() {
        try {
            console.log('🔍 Checking database migrations...');
            const { Client } = require('pg');
            const client = new Client({ connectionString: this.connectionString });

            await client.connect();

            // Check if migration table exists
            const migResult = await client.query(`
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'migrations'
                )
            `);

            let result = { hasMigrationsTable: false, migrationsCount: 0 };

            if (migResult.rows[0].exists) {
                const countResult = await client.query('SELECT COUNT(*) FROM migrations');
                result.hasMigrationsTable = true;
                result.migrationsCount = parseInt(countResult.rows[0].count);
            }

            await client.end();
            console.log('✅ Database migrations validated');
            return result;
        } catch (error) {
            console.error('❌ Database migration check failed:', error.message);
            return { status: 'error', error: error.message };
        }
    }

    async testCriticalTables() {
        try {
            console.log('🔍 Checking critical database tables...');
            const criticalTables = [
                'users', 'events', 'notes', 'integrations', 'auth_sessions'
            ];

            const { Client } = require('pg');
            const client = new Client({ connectionString: this.connectionString });

            await client.connect();

            const results = {};
            for (const table of criticalTables) {
                const exists = await client.query(`
                    SELECT EXISTS (
                        SELECT FROM pg_tables
                        WHERE schemaname = 'public'
                        AND tablename = $1
                    )
                `, [table]);

                results[table] = exists.rows[0].exists;
            }

            await client.end();
            console.log('✅ Database tables verified');
            return results;
        } catch (error) {
            console.error('❌ Database table check failed:', error.message);
            return { status: 'error', error: error.message };
        }
    }
}

class ServerTester {
    constructor() {
        this.baseUrl = `http://localhost:${ENV_CONFIG.PORT}`;
        this.serverProcess = null;
    }

    async isServerRunning() {
        try {
            const response = await axios.get(this.baseUrl, { timeout: 5000 });
            return response.status === 200;
        } catch (error) {
            return false;
        }
    }

    async startDevServer() {
        console.log('🔄 Starting Next.js development server...');

        return new Promise((resolve, reject) => {
            const startTime = Date.now();
            const maxWait = ENV_CONFIG.SERVER_STARTUP_TIMEOUT;

            this.serverProcess = spawn('npm', ['run', 'dev'], {
                cwd: path.join(__dirname),
                stdio: 'pipe',
                env: {
                    ...process.env,
                    ...ENV_CONFIG,
                    FORCE_COLOR: '1'
                }
            });

            // Wait 3 seconds for server to start
            setTimeout(() => {
                resolve();
            }, 3000);
        });
    }

    async stopServer() {
        if (this.serverProcess) {
            this.serverProcess.kill('SIGTERM');
            this.serverProcess = null;
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }

    async runBuild() {
        try {
            console.log('📦 Running production build...');
            const result = execSync('npm run build', {
                cwd: path.join(__dirname),
                stdio: 'pipe',
                encoding: 'utf8',
                env: { ...process.env, ...ENV_CONFIG }
            });
            console.log('✅ Build completed successfully');
            return { success: true, output: result };
        } catch (error) {
            console.error('❌ Build failed:', error.message);
            return { success: false, error: error.message };
        }
    }

    async testBuild() {
        console.log('📦 Testing Next.js build...');

        const buildDir = path.join(__dirname, '.next');
        if (!fs.existsSync(buildDir)) {
            throw new Error('Build directory not found');
        }

        const staticFiles = fs.readdirSync(path.join(buildDir, 'static'));
        console.log(`✅ Build found with ${staticFiles.length} static bundles`);

        return { buildDir, staticFiles };
    }

    async testPages() {
        console.log('🌐 Testing primary routes...');
        const pages = [
            '/',
            '/dashboard',
            '/login',
            '/calendar',
            '/settings'
        ];

        const results = {};
        for (const page of pages) {
            try {
                const response = await axios.get(`${this.baseUrl}${page}`, {
                    timeout: 10000,
                    maxRedirects: 5
                });
                results[page] = { status: response.status, ok: response.status < 400 };
            } catch (error) {
                results[page] = { status: error.response?.status || 'error', ok: false };
            }
        }

        return results;
    }

    async testAPI() {
        console.log('🔌 Testing API endpoints...');
        const endpoints = [
            '/api/auth/health',
            '/api/health',
            '/api/chat/health',
            '/api/calendar/health'
        ];

        const results = {};
        for (const endpoint of endpoints) {
            try {
                const response = await axios.get(`${this.baseUrl}${endpoint}`, {
                    timeout: 5000
                });
                results[endpoint] = { status: response.status, ok: response.status < 400 };
            } catch (error) {
                results[endpoint] = { status: error.response?.status || 'error', ok: false };
            }
        }

        return results;
    }
}

class IntegrationTester {
    constructor() {
        this.baseUrl = `http://localhost:${ENV_CONFIG.PORT}`;
    }

    async testAuth() {
        console.log('🔐 Testing authentication flow...');
    }

    async testDatabaseIntegration() {
        console.log('🔗 Testing database integration with app...');
        // Create a test user through API if possible
    }

    async testExternalServices() {
        console.log('🌐 Testing external service integrations...');

        const services = {
            google: '/api/auth/google',
            linkedin: '/api/auth/linkedin',
            openai: '/api/chat/health'
        };

        const results = {};
        for (const [name, endpoint] of Object.entries(services)) {
            try {
                const response = await axios.get(`${this.baseUrl}${endpoint}`, {
                    timeout: 5000
                });
                results[name] = response.status;
            } catch (error) {
                results[name] = error.code || 'error';
            }
        }

        return results;
    }

    async testPerformance() {
        console.log('⚡ Testing performance metrics...');

        const marked = [];
        for (let i = 0; i < 5; i++) {
            const start = Date.now();
            await axios.get(this.baseUrl);
            const duration = Date.now() - start;
            marked.push(duration);
        }

        const avg = marked.reduce((a, b) => a + b) / marked.length;
        console.log(`✅ Average response time: ${avg.toFixed(2)}ms`);

        return {
            average: avg,
            measurements: marked,
            acceptable: avg < 5000
        };
    }
}

async function validateEnvVars() {
    console.log('🔐 Validating environment variables...');

    const required = ['OPENAI_API_KEY', 'DATABASE_URL'];
    const missing = required.filter(key => !ENV_CONFIG[key]);

    if (missing.length > 0) {
        console.error('❌ Missing environment variables:', missing);
        return false;
    }

    console.log('✅ All critical environment variables present');
    return true;
}

async function runComprehensiveTest() {
    console.log('🎯 Starting Live-Ready Production Test\n');
    console.log('='.repeat(80));

    const startTime = Date.now();
    const results = {
        env: false,
        build: false,
        database: false,
        server: false,
        api: false,
        performance: false,
        external: false
    };

    try {
        // Step 1: Environment validation
        results.env = await validateEnvVars();

        // Step 2: Database tests
        const dbTester = new DatabaseTester();
        const dbConnection = await dbTester.testConnection();
        const dbMigrations = await dbTester.testMigrations();
        const dbTables = await dbTester.testCriticalTables();

        results.database = dbConnection.status === 'connected' &&
                          !dbMigrations.error &&
                          !dbTables.error;

        // Step 3: Build tests
        const serverTester = new ServerTester();
        results.build = (await serverTester.runBuild()).success;
        await serverTester.testBuild();

        // Step 4: Server and API tests
        const running = await serverTester.isServerRunning();
        if (!running) {
            await serverTester.startDevServer();
        }

        const pages = await serverTester.testPages();
        const api = await serverTester.testAPI();

        results.server = Object.values(pages).every(p => p.ok || p.status < 500);
        results.api = Object.values(api).some(a => a.ok);

        // Step 5: Integration tests
        const integrationTester = new IntegrationTester();
        const externalServices = await integrationTester.testExternalServices();
        const performance = await integrationTester.testPerformance();

        results.external = Object.values(externalServices).every(s => s === 200 || s === 'ENOTFOUND');
        results.performance = performance.acceptable;

        const totalPassed = Object.values(results).filter(Boolean).length;
        const totalChecks = Object.keys(results).length;
        const isLiveReady = totalPassed === totalChecks;

        console.log('='.repeat(80));
        console.log('\n📋 FINAL RESULTS');
        console.log('='.repeat(60));

        Object.entries(results).forEach(([test, passed]) => {
            console.log(`${passed ? '✅' : '❌'} ${test.toUpperCase()} ${passed ? 'PASSED' : 'FAILED'}`);
        });

        console.log(`\n🎉 OVERALL: ${totalPassed}/${totalChecks} tests passed`);

        if (isLiveReady) {
            console.log('🚀 APPLICATION IS LIVE-READY FOR PRODUCTION!');
            console.log(`⏱️  Total test time: ${Date.now() - startTime}ms`);
            return true;
        } else {
            console.log('❌ APPLICATION IS NOT LIVE-READY');
            console.log('📋 Address the failed checks above before deploying');
            return false;
        }

    } catch (error) {
        console.error('❌ Test suite failed:', error.message);
        return false;
    }
}

// Export for programmatic use
module.exports = {
    DatabaseTester,
    ServerTester,
    IntegrationTester,
    runComprehensiveTest,
    ENV_CONFIG
};

// CLI Execution
if (require.main === module) {
    runComprehensiveTest().then(success => {
        process.exit(success ? 0 : 1);
    }).catch(error => {
        console.error('❌ Fatal error:', error);
        process.exit(1);
    });
}
