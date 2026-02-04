/**
 * Simple Smoke Test for Atom AI Integration Test Setup
 * Verifies that the test environment is properly configured
 */

const axios = require("axios");
const MockServer = require("./mock-server");

// Test configuration
const TEST_CONFIG = {
  baseUrl: process.env.TEST_BASE_URL || "http://localhost:3000",
  timeout: 10000,
  retries: 3,
};

class SmokeTestHelper {
  constructor() {
    this.testResults = [];
    this.passed = 0;
    this.failed = 0;
    this.mockServer = null;
  }

  async makeRequest(method, endpoint, data = null) {
    const url = `${TEST_CONFIG.baseUrl}${endpoint}`;
    const config = {
      method,
      url,
      timeout: TEST_CONFIG.timeout,
      validateStatus: () => true, // Don't throw on error status codes
    };

    if (data) {
      config.data = data;
    }

    try {
      const response = await axios(config);
      return response;
    } catch (error) {
      throw new Error(`API request failed: ${error.message}`);
    }
  }

  async healthCheck() {
    try {
      const response = await this.makeRequest("GET", "/api/health");
      return response.status < 400;
    } catch {
      return false;
    }
  }

  async startMockServer() {
    try {
      // Check if real server is running
      const response = await axios.get(`${TEST_CONFIG.baseUrl}/api/health`, {
        timeout: 2000,
        validateStatus: () => true,
      });

      if (response.status < 400) {
        console.log("✅ Using existing backend server");
        return false;
      }
    } catch (error) {
      // Real server not available, start mock server
      console.log("🚀 Starting mock server for testing...");
      this.mockServer = new MockServer(3000);
      await this.mockServer.start();
      console.log("✅ Mock server started on port 3000");
      return true;
    }
    return false;
  }

  async stopMockServer() {
    if (this.mockServer) {
      await this.mockServer.stop();
      console.log("🛑 Mock server stopped");
      this.mockServer = null;
    }
  }

  async waitForService(retries = 5, delay = 2000) {
    for (let i = 0; i < retries; i++) {
      if (await this.healthCheck()) {
        return true;
      }
      console.log(`Waiting for service... (${i + 1}/${retries})`);
      await new Promise((resolve) => setTimeout(resolve, delay));
    }
    return false;
  }

  async runTest(name, testFunction) {
    console.log(`🧪 Running test: ${name}`);

    try {
      const start = Date.now();
      const result = await testFunction();
      const duration = Date.now() - start;

      this.passed++;
      console.log(`   ✅ ${name} passed (${duration}ms)`);
      this.testResults.push({ name, status: "PASSED", duration });
      return true;
    } catch (error) {
      this.failed++;
      console.error(`   ❌ ${name} failed: ${error.message}`);
      this.testResults.push({ name, status: "FAILED", error: error.message });
      return false;
    }
  }

  printSummary() {
    console.log("\n📊 Smoke Test Summary:");
    console.log("═".repeat(40));
    console.log(`Total Tests: ${this.testResults.length}`);
    console.log(`✅ Passed: ${this.passed}`);
    console.log(`❌ Failed: ${this.failed}`);
    console.log("═".repeat(40));

    if (this.failed > 0) {
      console.log("\nFailed Tests:");
      this.testResults
        .filter((r) => r.status === "FAILED")
        .forEach((test, index) => {
          console.log(`${index + 1}. ${test.name}: ${test.error}`);
        });
      process.exit(1);
    } else {
      console.log("🎉 All smoke tests passed!");
      process.exit(0);
    }
  }
}

async function runSmokeTests() {
  const helper = new SmokeTestHelper();
  let usingMockServer = false;

  console.log("🚀 Starting Smoke Tests...\n");

  try {
    // Start mock server if needed
    usingMockServer = await helper.startMockServer();

    // Check if service is available
    const serviceAvailable = await helper.waitForService();
    if (!serviceAvailable) {
      console.warn("⚠️  Service not available, running in offline mode");
    }

    await helper.runTest("Environment variables", async () => {
      const requiredVars = ["NODE_ENV"];
      const missingVars = requiredVars.filter(
        (varName) => !process.env[varName],
      );

      if (missingVars.length > 0) {
        throw new Error(
          `Missing environment variables: ${missingVars.join(", ")}`,
        );
      }
    });

    await helper.runTest("Service health endpoint", async () => {
      const response = await helper.makeRequest("GET", "/api/health");

      if (response.status >= 400) {
        throw new Error(`Health check failed with status ${response.status}`);
      }

      if (!response.data) {
        throw new Error("Health check response missing data");
      }
    });

    await helper.runTest("Database health endpoint", async () => {
      const response = await helper.makeRequest("GET", "/api/health/db");

      // Should respond with some status code
      if (response.status >= 500) {
        throw new Error(
          `Database health check failed with status ${response.status}`,
        );
      }
    });

    await helper.runTest("Authentication service", async () => {
      const response = await helper.makeRequest("GET", "/api/auth/health");

      if (response.status >= 500) {
        throw new Error(`Auth service failed with status ${response.status}`);
      }
    });

    await helper.runTest("Core API endpoints", async () => {
      const endpoints = ["/api/workflows", "/api/budgets", "/api/automation"];

      for (const endpoint of endpoints) {
        const response = await helper.makeRequest("GET", endpoint);

        if (response.status >= 500) {
          throw new Error(
            `Endpoint ${endpoint} server error: ${response.status}`,
          );
        }
      }
    });

    await helper.runTest("Error handling consistency", async () => {
      const response = await helper.makeRequest("POST", "/api/auth/login", {
        invalid: "data",
      });

      if (response.status >= 400) {
        if (!response.data || typeof response.data !== "object") {
          throw new Error("Error response should be a JSON object");
        }
      }
    });

    helper.printSummary();
  } finally {
    if (usingMockServer) {
      await helper.stopMockServer();
    }
  }
}

// Run if called directly
if (require.main === module) {
  runSmokeTests().catch((error) => {
    console.error("❌ Smoke test suite failed:", error.message);
    process.exit(1);
  });
}

module.exports = {
  SmokeTestHelper,
  runSmokeTests,
};
