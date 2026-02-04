/**
 * Simple Integration Test for Atom AI Assistant
 * Tests core functionality without Jest dependencies
 */

const axios = require("axios");
const MockServer = require("./mock-server");

// Test configuration
const TEST_CONFIG = {
  baseUrl: process.env.TEST_BASE_URL || "http://localhost:3000",
  timeout: 10000,
};

// Test utilities
class TestHelper {
  constructor() {
    this.passed = 0;
    this.failed = 0;
    this.total = 0;
    this.mockServer = null;
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

  async makeRequest(method, endpoint, data = null) {
    const url = `${TEST_CONFIG.baseUrl}${endpoint}`;
    const config = {
      method,
      url,
      timeout: TEST_CONFIG.timeout,
      validateStatus: () => true,
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

  async runTest(name, testFunction) {
    this.total++;
    console.log(`🧪 Running test: ${name}`);

    try {
      const start = Date.now();
      const result = await testFunction();
      const duration = Date.now() - start;

      this.passed++;
      console.log(`   ✅ ${name} passed (${duration}ms)`);
      return { success: true, result, duration };
    } catch (error) {
      this.failed++;
      console.error(`   ❌ ${name} failed: ${error.message}`);
      return { success: false, error: error.message };
    }
  }

  printSummary() {
    console.log("\n📊 Test Summary:");
    console.log("═".repeat(40));
    console.log(`Total Tests: ${this.total}`);
    console.log(`✅ Passed: ${this.passed}`);
    console.log(`❌ Failed: ${this.failed}`);
    console.log("═".repeat(40));

    if (this.failed > 0) {
      process.exit(1);
    } else {
      process.exit(0);
    }
  }
}

// Test functions
async function runIntegrationTests() {
  const helper = new TestHelper();
  let usingMockServer = false;

  try {
    usingMockServer = await helper.startMockServer();

    // Health check tests
    await helper.runTest("Health Check", async () => {
      const response = await helper.makeRequest("GET", "/api/health");
      if (response.status >= 400) {
        throw new Error(`Health check failed with status ${response.status}`);
      }
      return response.data;
    });

    await helper.runTest("Database Health", async () => {
      const response = await helper.makeRequest("GET", "/api/health/db");
      if (response.status >= 400) {
        throw new Error(
          `Database health check failed with status ${response.status}`,
        );
      }
      return response.data;
    });

    // Authentication tests
    await helper.runTest("Authentication Health", async () => {
      const response = await helper.makeRequest("GET", "/api/auth/health");
      if (response.status >= 500) {
        throw new Error(
          `Auth health check failed with status ${response.status}`,
        );
      }
      return response.data;
    });

    await helper.runTest("User Signup", async () => {
      const response = await helper.makeRequest("POST", "/api/auth/signup", {
        email: "test@example.com",
        password: "TestPass123!",
        name: "Test User",
        persona: "alex",
      });

      if (response.status >= 400) {
        throw new Error(`Signup failed with status ${response.status}`);
      }
      return response.data;
    });

    await helper.runTest("User Login", async () => {
      const response = await helper.makeRequest("POST", "/api/auth/login", {
        email: "test@example.com",
        password: "TestPass123!",
      });

      if (response.status >= 400) {
        throw new Error(`Login failed with status ${response.status}`);
      }
      return response.data;
    });

    // Workflow tests
    await helper.runTest("Create Workflow", async () => {
      const response = await helper.makeRequest("POST", "/api/workflows", {
        name: "Test Workflow",
        description: "Test workflow creation",
        triggers: ["manual"],
        actions: ["test-action"],
        type: "test",
      });

      if (response.status >= 400) {
        throw new Error(
          `Workflow creation failed with status ${response.status}`,
        );
      }
      return response.data;
    });

    await helper.runTest("List Workflows", async () => {
      const response = await helper.makeRequest("GET", "/api/workflows");
      if (response.status >= 500) {
        throw new Error(`Workflow list failed with status ${response.status}`);
      }
      return response.data;
    });

    // Budget tests
    await helper.runTest("Create Budget", async () => {
      const response = await helper.makeRequest("POST", "/api/budgets", {
        name: "Test Budget",
        amount: 1000,
        categories: ["test"],
        alerts: true,
      });

      if (response.status >= 400) {
        throw new Error(
          `Budget creation failed with status ${response.status}`,
        );
      }
      return response.data;
    });

    await helper.runTest("List Budgets", async () => {
      const response = await helper.makeRequest("GET", "/api/budgets");
      if (response.status >= 500) {
        throw new Error(`Budget list failed with status ${response.status}`);
      }
      return response.data;
    });

    // Analytics tests
    await helper.runTest("Workflow Analytics", async () => {
      const response = await helper.makeRequest(
        "GET",
        "/api/analytics/workflows",
      );
      if (response.status >= 500) {
        throw new Error(`Analytics failed with status ${response.status}`);
      }
      return response.data;
    });

    helper.printSummary();
  } finally {
    if (usingMockServer) {
      await helper.stopMockServer();
    }
  }
}

// Main execution
if (require.main === module) {
  console.log("🚀 Starting Simple Integration Tests\n");
  console.log("═".repeat(50));

  runIntegrationTests().catch((error) => {
    console.error("❌ Test suite failed:", error.message);
    process.exit(1);
  });
}

module.exports = {
  TestHelper,
  runIntegrationTests,
};
