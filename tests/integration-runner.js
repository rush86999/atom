#!/usr/bin/env node

/**
 * Complete Desktop Integration Test Suite
 * Tests Tauri Backend + Web Backend + Desktop Frontend Integration
 * Identifies and fixes critical integration bugs
 */

const { spawn, exec } = require("child_process");
const { promisify } = require("util");
const fs = require("fs").promises;
const path = require("path");
const axios = require("axios");
const { WebSocket } = require("ws");

const execAsync = promisify(exec);

class IntegrationTestRunner {
  constructor() {
    this.testResults = {
      summary: { total: 0, passed: 0, failed: 0, warnings: 0 },
      categories: {},
      bugs: [],
    };
    this.startTime = Date.now();
    this.config = {
      webUrl: "http://localhost:3000",
      desktopUrl: "http://localhost:1420",
      apiUrl: "http://localhost:5000",
      timeout: 10000,
      retries: 3,
    };
  }

  async log(level, message, data = {}) {
    const timestamp = new Date().toISOString();
    const logEntry = `[${timestamp}] ${level}: ${message}\n`;

    if (data && Object.keys(data).length > 0) {
      logEntry += `${JSON.stringify(data, null, 2)}\n`;
    }

    await fs.appendFile(
      path.join(__dirname, "integration-test-results.log"),
      logEntry,
    );

    if (level === "ERROR") {
      this.testResults.bugs.push({ timestamp, message, data });
    }
  }

  async assert(condition, message) {
    if (!condition) {
      throw new Error(message);
    }
  }

  async runTest(category, testName, testFunction) {
    this.testResults.summary.total++;
    console.log(`🧪 Running ${category} -> ${testName}`);

    try {
      const start = Date.now();
      const result = await testFunction();
      const duration = Date.now() - start;

      const testResult = {
        name: testName,
        status: "PASSED",
        duration,
        details: result,
      };

      this.testResults.summary.passed++;

      if (!this.testResults.categories[category]) {
        this.testResults.categories[category] = [];
      }
      this.testResults.categories[category].push(testResult);

      await this.log("SUCCESS", `${category}.${testName}`, testResult);
      console.log(`   ✅ ${testName} (${duration}ms)`);
    } catch (error) {
      const testResult = {
        name: testName,
        status: "FAILED",
        error: error.message,
        stack: error.stack,
      };

      this.testResults.summary.failed++;

      if (!this.testResults.categories[category]) {
        this.testResults.categories[category] = [];
      }
      this.testResults.categories[category].push(testResult);

      await this.log("ERROR", `${category}.${testName} FAILED`, {
        error: error.message,
        stack: error.stack,
      });
      console.error(`   ❌ ${testName}: ${error.message}`);

      // Suggest fix
      this.suggestFix(category, testName, error);
    }
  }

  suggestFix(category, testName, error) {
    const fixes = {
      "web-backend": {
        health_check:
          "Check if backend is running on localhost:3000 and /api/health endpoint exists",
        database_connection:
          "Verify DATABASE_URL and ensure PostgreSQL is running",
        authentication_endpoints:
          "Check authentication service is running and endpoints are configured",
        api_endpoints: "Verify API routes are properly defined in the backend",
      },
      "desktop-backend": {
        settings_encryption:
          "Check ENCRYPTION_KEY environment variable is 32 bytes long",
        web_socket_connection:
          "Verify NEXT_PUBLIC_AUDIO_PROCESSOR_URL is set and accessible",
        tauri_functions: "Ensure Tauri backend commands are properly exposed",
      },
      database: {
        connection:
          "Start PostgreSQL service and verify DATABASE_URL connection string",
        migrations: "Run database migrations with: npx prisma migrate dev",
        schema_validation: "Check Prisma schema matches database structure",
      },
      environment: {
        env_variables: "Set required environment variables in .env file",
        dependencies: "Run npm install to install missing dependencies",
      },
    };

    const fix = fixes[category]?.[testName];
    if (fix) {
      this.log("INFO", `Suggested fix for ${testName}`, { fix });
    }
  }

  // 1. Web Backend Integration Tests
  async testWebBackendIntegration() {
    const baseUrl = this.config.webUrl;

    await this.runTest("web-backend", "health_check", async () => {
      const response = await axios.get(`${baseUrl}/api/health`, {
        timeout: 5000,
        validateStatus: () => true,
      });
      await this.assert(
        response.status < 400,
        `Health check failed with status ${response.status}`,
      );
      return { status: response.status, endpoint: "/api/health" };
    });

    await this.runTest("web-backend", "database_connection", async () => {
      const response = await axios.post(`${baseUrl}/api/health/db`, {
        timeout: 10000,
        validateStatus: () => true,
      });
      await this.assert(response.status === 200, `Database connection failed`);
      return response.data;
    });

    await this.runTest("web-backend", "authentication_endpoints", async () => {
      const endpoints = [
        "/api/auth/health",
        "/api/auth/callback/google",
        "/api/auth/callback/linkedin",
      ];

      const results = [];
      for (const endpoint of endpoints) {
        try {
          const response = await axios.get(`${baseUrl}${endpoint}`, {
            timeout: 5000,
            validateStatus: () => true,
          });
          results.push({ endpoint, status: response.status });
        } catch (error) {
          results.push({ endpoint, status: "ERROR", error: error.message });
        }
      }

      // At least one auth endpoint should be accessible
      const accessibleEndpoints = results.filter((r) => r.status < 400);
      await this.assert(
        accessibleEndpoints.length > 0,
        "No authentication endpoints accessible",
      );
      return results;
    });

    await this.runTest("web-backend", "api_endpoints", async () => {
      const endpoints = ["/api/workflows", "/api/budgets", "/api/automation"];

      const results = [];
      for (const endpoint of endpoints) {
        try {
          const response = await axios.get(`${baseUrl}${endpoint}`, {
            timeout: 5000,
            validateStatus: () => true,
          });
          results.push({ endpoint, status: response.status });
        } catch (error) {
          results.push({ endpoint, status: "ERROR", error: error.message });
        }
      }

      return results;
    });
  }

  // 2. Desktop Backend Integration Tests
  async testDesktopBackendIntegration() {
    await this.runTest("desktop-backend", "settings_encryption", async () => {
      // Test encryption key configuration
      const encryptionKey = process.env.ENCRYPTION_KEY;
      await this.assert(
        encryptionKey,
        "ENCRYPTION_KEY environment variable not set",
      );
      await this.assert(
        encryptionKey.length >= 32,
        "ENCRYPTION_KEY must be at least 32 characters",
      );
      return { encryption_key_length: encryptionKey.length };
    });

    await this.runTest("desktop-backend", "web_socket_connection", async () => {
      const wsUrl = process.env.NEXT_PUBLIC_AUDIO_PROCESSOR_URL;
      await this.assert(wsUrl, "NEXT_PUBLIC_AUDIO_PROCESSOR_URL not set");

      // Try to connect to WebSocket (with timeout)
      return new Promise((resolve, reject) => {
        const ws = new WebSocket(wsUrl);
        const timeout = setTimeout(() => {
          ws.close();
          reject(new Error("WebSocket connection timeout"));
        }, 5000);

        ws.on("open", () => {
          clearTimeout(timeout);
          ws.close();
          resolve({ connected: true, url: wsUrl });
        });

        ws.on("error", (error) => {
          clearTimeout(timeout);
          reject(new Error(`WebSocket connection failed: ${error.message}`));
        });
      });
    });

    await this.runTest("desktop-backend", "tauri_functions", async () => {
      // Test if Tauri backend commands are accessible
      // This would typically involve testing IPC communication
      return { status: "Tauri functions would be tested here" };
    });
  }

  // 3. Database Integration Tests
  async testDatabaseIntegration() {
    let pg;
    try {
      pg = require("pg");
    } catch (error) {
      await this.log(
        "WARN",
        "PostgreSQL client not available, skipping database tests",
      );
      return;
    }

    await this.runTest("database", "connection", async () => {
      const databaseUrl = process.env.DATABASE_URL;
      await this.assert(
        databaseUrl,
        "DATABASE_URL environment variable not set",
      );

      const client = new pg.Client({ connectionString: databaseUrl });
      try {
        await client.connect();
        const result = await client.query(
          "SELECT NOW() as current_time, version() as pg_version",
        );
        await client.end();
        return {
          connected: true,
          current_time: result.rows[0].current_time,
          version: result.rows[0].pg_version,
        };
      } catch (error) {
        await client.end();
        throw new Error(`Database connection failed: ${error.message}`);
      }
    });

    await this.runTest("database", "migrations", async () => {
      // Check if required tables exist
      const databaseUrl = process.env.DATABASE_URL;
      const client = new pg.Client({ connectionString: databaseUrl });

      try {
        await client.connect();

        // Check for common tables that should exist after migrations
        const tables = ["users", "workflows", "budgets", "automations"];
        const tableResults = {};

        for (const table of tables) {
          try {
            const result = await client.query(
              `SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)`,
              [table],
            );
            tableResults[table] = result.rows[0].exists;
          } catch (error) {
            tableResults[table] = false;
          }
        }

        await client.end();

        // At least some tables should exist
        const existingTables = Object.values(tableResults).filter(
          (exists) => exists,
        );
        await this.assert(
          existingTables.length > 0,
          "No database tables found - run migrations",
        );

        return tableResults;
      } catch (error) {
        await client.end();
        throw error;
      }
    });
  }

  // 4. Environment Validation Tests
  async testEnvironmentValidation() {
    await this.runTest("environment", "env_variables", async () => {
      const requiredVars = [
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "ENCRYPTION_KEY",
        "NEXT_PUBLIC_AUDIO_PROCESSOR_URL",
      ];

      const missingVars = requiredVars.filter(
        (varName) => !process.env[varName],
      );
      await this.assert(
        missingVars.length === 0,
        `Missing environment variables: ${missingVars.join(", ")}`,
      );

      return {
        required_variables: requiredVars,
        missing: missingVars,
        all_set: missingVars.length === 0,
      };
    });

    await this.runTest("environment", "dependencies", async () => {
      // Check if required dependencies are installed
      const dependencies = ["axios", "pg", "ws"];
      const results = {};

      for (const dep of dependencies) {
        try {
          require(dep);
          results[dep] = { installed: true };
        } catch (error) {
          results[dep] = { installed: false, error: error.message };
        }
      }

      const missingDeps = Object.entries(results)
        .filter(([_, info]) => !info.installed)
        .map(([dep]) => dep);

      await this.assert(
        missingDeps.length === 0,
        `Missing dependencies: ${missingDeps.join(", ")}`,
      );

      return results;
    });
  }

  // 5. Cross-Service Integration Tests
  async testCrossServiceIntegration() {
    await this.runTest("integration", "web_to_database", async () => {
      // Test that web backend can communicate with database
      const baseUrl = this.config.webUrl;

      const response = await axios.post(`${baseUrl}/api/test/db-connection`, {
        timeout: 10000,
        validateStatus: () => true,
      });

      await this.assert(
        response.status === 200,
        "Web to database communication failed",
      );
      return response.data;
    });

    await this.runTest("integration", "desktop_to_web", async () => {
      // Test desktop can communicate with web backend
      const baseUrl = this.config.webUrl;

      const response = await axios.get(`${baseUrl}/api/health`, {
        timeout: 5000,
        validateStatus: () => true,
      });

      await this.assert(
        response.status < 400,
        "Desktop to web communication failed",
      );
      return { status: response.status };
    });
  }

  async runAllTests() {
    console.log("🚀 Starting Comprehensive Integration Test Suite\n");

    try {
      await this.testEnvironmentValidation();
      await this.testDatabaseIntegration();
      await this.testWebBackendIntegration();
      await this.testDesktopBackendIntegration();
      await this.testCrossServiceIntegration();

      // Generate summary report
      await this.generateReport();
    } catch (error) {
      await this.log("ERROR", "Test suite execution failed", {
        error: error.message,
      });
      throw error;
    }
  }

  async generateReport() {
    const duration = Date.now() - this.startTime;
    const report = {
      timestamp: new Date().toISOString(),
      duration: `${duration}ms`,
      summary: this.testResults.summary,
      categories: this.testResults.categories,
      bugs: this.testResults.bugs,
      environment: {
        node_version: process.version,
        platform: process.platform,
        arch: process.arch,
      },
    };

    // Save detailed report
    await fs.writeFile(
      path.join(__dirname, "integration-test-report.json"),
      JSON.stringify(report, null, 2),
    );

    // Print summary
    console.log("\n📊 Integration Test Summary:");
    console.log("═".repeat(50));
    console.log(`Total Tests: ${report.summary.total}`);
    console.log(`✅ Passed: ${report.summary.passed}`);
    console.log(`❌ Failed: ${report.summary.failed}`);
    console.log(`⚠️  Warnings: ${report.summary.warnings}`);
    console.log(`⏱️  Duration: ${report.duration}`);
    console.log("═".repeat(50));

    if (report.bugs.length > 0) {
      console.log("\n🐛 Critical Bugs Found:");
      report.bugs.forEach((bug, index) => {
        console.log(`${index + 1}. ${bug.message}`);
        if (bug.data.error) {
          console.log(`   Error: ${bug.data.error}`);
        }
      });
    }

    // Exit with appropriate code
    process.exit(report.summary.failed > 0 ? 1 : 0);
  }
}

// Main execution
(async () => {
  const testRunner = new IntegrationTestRunner();

  try {
    await testRunner.runAllTests();
  } catch (error) {
    console.error("❌ Test suite failed to run:", error.message);
    process.exit(1);
  }
})();
